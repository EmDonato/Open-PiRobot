"""Verify the robot command route on an isolated Docker network, without motors."""
import math
import time
import rclpy
from geometry_msgs.msg import Twist, TwistStamped
from sensor_msgs.msg import Joy
from std_msgs.msg import String


def main():
    rclpy.init()
    node = rclpy.create_node('jazzy_command_contract_smoke')
    commands, sources = [], []
    node.create_subscription(TwistStamped, '/cmd_vel', commands.append, 10)
    node.create_subscription(String, '/cmd_vel/selected_source', lambda m: sources.append(m.data), 10)
    navigation = node.create_publisher(Twist, '/cmd_vel/navigation', 10)
    joystick = node.create_publisher(Joy, '/joy', 10)

    def phase(expected, manual=False, navigation_on=True):
        commands.clear()
        sources.clear()
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            if navigation_on:
                message = Twist()
                message.linear.x = 0.04
                navigation.publish(message)
            if manual:
                message = Joy()
                message.header.stamp = node.get_clock().now().to_msg()
                message.axes = [0.0, 0.5, 0.0, 0.0, 0.0, 0.0]
                message.buttons = [0] * 12
                message.buttons[9] = 1
                joystick.publish(message)
            rclpy.spin_once(node, timeout_sec=0.05)
            if not commands or expected not in sources:
                continue
            command = commands[-1]
            value = command.twist.linear.x
            assert math.isfinite(value)
            if expected == 'navigation' and math.isclose(value, 0.04, abs_tol=1e-6):
                return
            if expected == 'manual' and 0.04 < value <= 0.20:
                assert command.header.stamp.sec > 0
                return
            if expected == 'stop' and value == 0.0 and command.twist.angular.z == 0.0:
                return
        raise AssertionError((expected, sources[-5:], [m.twist.linear.x for m in commands[-5:]]))

    try:
        phase('navigation')
        phase('manual', manual=True)
        phase('navigation')
        phase('stop', navigation_on=False)
        print('PASS: Nav2 Twist -> stamped mux output, manual priority, timeout release and stop')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
