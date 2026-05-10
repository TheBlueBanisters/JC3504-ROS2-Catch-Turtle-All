from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    turtlesim = Node(
        package="turtlesim",
        executable="turtlesim_node",
        name="sim",
        output="screen",
    )

    controller = Node(
        package="catch_turtle_all",
        executable="catch_turtle_node",
        name="catch_turtle_controller",
        output="screen",
    )

    return LaunchDescription(
        [
            turtlesim,
            controller,
        ]
    )
