# Euler angles of the corrected /imu quaternion, for diagnostics.
# Fixed-axis roll (X), pitch (Y), yaw (Z), with the same timestamp/frame as /imu.
# Angles wrap; pitch has the usual Euler singularity at +/-90 degrees.
# Does not imply that /imu orientation is enabled for fusion.
std_msgs/Header header
float64 roll_rad
float64 pitch_rad
float64 yaw_rad
float64 roll_deg
float64 pitch_deg
float64 yaw_deg
