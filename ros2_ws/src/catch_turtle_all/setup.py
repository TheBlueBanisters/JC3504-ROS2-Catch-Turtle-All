from glob import glob
from setuptools import find_packages, setup

package_name = "catch_turtle_all"

setup(
    name=package_name,
    version="0.0.1",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/launch", glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="student",
    maintainer_email="student@example.com",
    description="Catch Turtle All assignment for ROS2 turtlesim.",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "catch_turtle_node = catch_turtle_all.catch_turtle_node:main",
        ],
    },
)
