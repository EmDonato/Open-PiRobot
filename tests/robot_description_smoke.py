"""Validate the installed robot model and its OBJ/MTL resources without hardware."""
from pathlib import Path
import xml.etree.ElementTree as ET
from ament_index_python.packages import get_package_share_directory
import xacro


def main():
    share = Path(get_package_share_directory('robot_descriptor'))
    robot = ET.fromstring(xacro.process_file(
        str(share / 'descriptor/robot.urdf.xacro'),
        mappings={'use_sim_camera': 'false', 'sim_mode': 'false'}).toxml())
    links = {link.attrib['name'] for link in robot.findall('link')}
    parents = {}
    for joint in robot.findall('joint'):
        parent = joint.find('parent').attrib['link']
        child = joint.find('child').attrib['link']
        assert parent in links and child in links
        assert child not in parents, child
        parents[child] = parent
    for link in links:
        seen = set()
        while link != 'base_link':
            assert link not in seen and link in parents, (link, parents)
            seen.add(link)
            link = parents[link]
    meshes = set()
    for mesh in robot.findall('.//mesh'):
        uri = mesh.attrib['filename']
        prefix = 'package://robot_descriptor/'
        assert uri.startswith(prefix), uri
        resource = share / uri.removeprefix(prefix)
        assert resource.is_file(), resource
        meshes.add(resource.name)
        if resource.suffix == '.obj':
            for line in resource.read_text().splitlines():
                if line.startswith('mtllib '):
                    assert (resource.parent / line.removeprefix('mtllib ').strip()).is_file(), line
    assert {'chassis_diff_wheel_robot.obj', 'wheel_left.obj', 'lidar_LD06.obj', 'realsense.obj'} <= meshes
    assert 'imu_link' not in parents, 'The physical IMU mounting TF belongs to the STM32 driver'
    print('PASS: installed new Xacro, connected single-parent TF tree and all OBJ/MTL resources')


if __name__ == '__main__':
    main()
