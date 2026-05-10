# JC3504 ROS2 Catch Turtle All

This repository contains the coursework project for **JC3504 Robot Technology**.  
The project implements a "Catch Turtle All" simulation using **ROS2 Humble** and **Turtlesim**.

## Project Overview

The objective of this project is to control a master turtle in the Turtlesim environment so that it can automatically catch randomly spawned turtles. Once a turtle is caught, it joins a follower chain behind the master turtle.

The system mainly implements the following functions:

- Spawn a new target turtle at a random position every 3 seconds.
- Control the master turtle to move towards and catch the nearest available target turtle.
- Add caught turtles into a chain formation, where each turtle follows the turtle directly in front of it.
- Run the whole simulation through a launch file.

## Environment

The project was developed and tested under:

- Ubuntu 22.04
- ROS2 Humble
- Python 3
- Turtlesim

## Project Structure

```text
.
├── run.sh
└── ros2_ws
    └── src
        └── catch_turtle_all
            ├── catch_turtle_all
            │   └── catch_turtle_node.py
            ├── launch
            │   └── catch_turtle.launch.py
            ├── package.xml
            ├── setup.py
            ├── setup.cfg
            └── resource
```

## How to Run

First, make sure ROS2 Humble and Turtlesim are installed.

Then run the project from the root directory of this repository:

```bash
bash run.sh
```

The script will build the ROS2 package and start the simulation automatically.

Alternatively, the project can be run manually:

```bash
cd ros2_ws
source /opt/ros/humble/setup.bash
colcon build --packages-select catch_turtle_all
source install/setup.bash
ros2 launch catch_turtle_all catch_turtle.launch.py
```

## Main Features

### 1. Random Turtle Spawning

The system uses the Turtlesim `/spawn` service to create new target turtles at random valid positions. A new target turtle is generated every 3 seconds during the simulation.

### 2. Master Turtle Catching

The master turtle subscribes to turtle pose topics and selects the nearest waiting target. It then publishes velocity commands to move towards the selected turtle.

The master turtle first rotates to face the target and then moves forward to catch it.

### 3. Chain Formation

After a target turtle is caught, it remains visible in the simulation and becomes part of the follower chain.

The first caught turtle follows the master turtle, and each later turtle follows the turtle directly in front of it.

## Notes

The generated folders below are not included in the submitted source code because they can be recreated by running `colcon build`:

- `build/`
- `install/`
- `log/`

Python cache files are also unnecessary for submission:

- `__pycache__/`
- `*.pyc`

## Authors

Group 6

- WU SIYAN, ID: 50091024
- CHEN YIXIANG, ID: 50091017
- ZHU CHENGHUA, ID: 50090983
- ZHU HOUHUA, ID: 50090996
- LUO FAN, ID: 50091021
