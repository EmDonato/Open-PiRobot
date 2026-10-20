"""Check robot description and EKF with synthetic sensor data on an isolated domain.

Run in a Jazzy container alongside only robot bringup and EKF, without hardware.
Do not run this publisher on an operational robot's ROS domain.
"""

import math
import time

import rclpy
from geometry_msgs.msg import TwistStamped
from nav_msgs.msg import Odometry
from rclpy.qos import DurabilityPolicy, QoSProfile, qos_profile_sensor_data
from sensor_msgs.msg import Imu
from tf2_msgs.msg import TFMessage


def main():
    rclpy.init()
    node = rclpy.create_node('jazzy_graph_smoke')
    odometry, dynamic, static = [], [], []
    subscriptions = [
        node.create_subscription(Odometry, '/odom', odometry.append, 10),
        node.create_subscription(TFMessage, '/tf', dynamic.append, 10),
        node.create_subscription(
            TFMessage, '/tf_static', static.append,
            QoSProfile(depth=10, durability=DurabilityPolicy.TRANSIENT_LOCAL)),
    ]
    imu_publisher = node.create_publisher(Imu, '/imu', qos_profile_sensor_data)
    encoder_publisher = node.create_publisher(
        TwistStamped, '/enc/twist_meas', qos_profile_sensor_data)
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            stamp = node.get_clock().now().to_msg()
            imu = Imu()
            imu.header.stamp = stamp
            imu.header.frame_id = 'imu_link'
            imu.orientation_covariance[0] = -1.0
            imu.angular_velocity_covariance[8] = 0.0009
            imu.linear_acceleration.z = 9.80665
            encoder = TwistStamped()
            encoder.header.stamp = stamp
            encoder.header.frame_id = 'base_link'
            encoder.twist.linear.x = 0.05
            imu_publisher.publish(imu)
            encoder_publisher.publish(encoder)
            rclpy.spin_once(node, timeout_sec=0.02)
        assert len(odometry) >= 10, 'no sustained EKF odometry across containers'
        last = odometry[-1]
        assert last.header.frame_id == 'odom'
        assert last.child_frame_id == 'base_link'
        assert last.pose.pose.position.x > odometry[0].pose.pose.position.x
        assert all(math.isfinite(v) for v in last.pose.covariance)
        dynamic_edges = {(t.header.frame_id, t.child_frame_id)
                         for msg in dynamic for t in msg.transforms}
        assert ('odom', 'base_link') in dynamic_edges
        parents = {t.child_frame_id: t.header.frame_id
                   for msg in static for t in msg.transforms}
        for target in ['base_footprint', 'laser_link', 'chassis']:
            frame, seen = target, set()
            while frame != 'base_link':
                assert frame not in seen and frame in parents, (target, frame, parents)
                seen.add(frame)
                frame = parents[frame]
        print('PASS: cross-container sensor data, EKF odometry/TF, late static TF subscriber')
    finally:
        for subscription in subscriptions:
            node.destroy_subscription(subscription)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
