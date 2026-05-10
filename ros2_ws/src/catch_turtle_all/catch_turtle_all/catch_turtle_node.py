import math
import random
from functools import partial
from typing import Dict, List, Optional, Set, Tuple

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_srvs.srv import Empty
from turtlesim.msg import Pose
from turtlesim.srv import Kill, SetPen, Spawn


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def normalize_angle(angle: float) -> float:
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle < -math.pi:
        angle += 2.0 * math.pi
    return angle


class CatchTurtleNode(Node):
    MASTER_NAME = "master"

    def __init__(self) -> None:
        super().__init__("catch_turtle_controller")

        self.spawn_period = 3.0
        self.control_period = 0.05
        self.catch_radius = 0.72
        self.follow_distance = 0.85
        self.world_min = 1.4
        self.world_max = 9.4
        self.master_spawn_x = 5.5
        self.master_spawn_y = 5.5
        self.max_linear_speed = 2.2
        self.max_angular_speed = 5.0

        self.poses: Dict[str, Pose] = {}
        self.waiting_targets: Set[str] = set()
        self.chain: List[str] = []
        self.cmd_publishers = {}
        self.pen_clients = {}
        self.pose_subscriptions = []
        self.spawned_turtles: Set[str] = set()
        self.spawn_index = 0
        self.spawn_in_progress = False
        self.is_ready = False
        self.current_target_name: Optional[str] = None

        self.spawn_client = self.create_client(Spawn, "/spawn")
        self.kill_client = self.create_client(Kill, "/kill")
        self.clear_client = self.create_client(Empty, "/clear")

        self.spawn_timer = None
        self.control_timer = None

    def setup_game(self) -> None:
        self.get_logger().info("Waiting for turtlesim services...")
        self.spawn_client.wait_for_service()
        self.kill_client.wait_for_service()
        self.clear_client.wait_for_service()

        self._kill_default_turtle()
        self._clear_screen_sync()

        first_target_name = self._spawn_turtle_sync(
            self._next_target_name(),
            *self._random_spawn_pose(avoid_master_spawn=True),
        )
        self._register_turtle(first_target_name, waiting_target=True, wait_for_pen=True)

        master_name = self._spawn_turtle_sync(
            self.MASTER_NAME,
            self.master_spawn_x,
            self.master_spawn_y,
            0.0,
        )
        self._register_turtle(master_name, waiting_target=False, wait_for_pen=True)

        self._wait_for_pose(first_target_name)
        self._wait_for_pose(master_name)
        self._turn_pen_off(first_target_name, wait=True)
        self._turn_pen_off(master_name, wait=True)
        self._clear_screen_sync()
        self._turn_pen_off(first_target_name, wait=True)
        self._turn_pen_off(master_name, wait=True)
        self._select_next_target()

        self.is_ready = True
        self.spawn_timer = self.create_timer(self.spawn_period, self._spawn_target_async)
        self.control_timer = self.create_timer(self.control_period, self._control_loop)
        self.get_logger().info("Catch Turtle game started.")

    def _kill_default_turtle(self) -> None:
        request = Kill.Request()
        request.name = "turtle1"
        future = self.kill_client.call_async(request)
        rclpy.spin_until_future_complete(self, future, timeout_sec=3.0)
        if future.result() is None:
            self.get_logger().warn("Could not remove turtle1; continuing anyway.")

    def _spawn_turtle_sync(self, name: str, x: float, y: float, theta: float) -> str:
        request = Spawn.Request()
        request.x = float(x)
        request.y = float(y)
        request.theta = float(theta)
        request.name = name

        future = self.spawn_client.call_async(request)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)
        result = future.result()
        if result is None:
            raise RuntimeError(f"Failed to spawn turtle {name}")
        self._remember_pose(result.name, x, y, theta)
        return result.name

    def _spawn_target_async(self) -> None:
        if self.spawn_in_progress:
            return

        self.spawn_in_progress = True
        name = self._next_target_name()
        x, y, theta = self._random_spawn_pose(avoid_master_spawn=True)

        request = Spawn.Request()
        request.x = float(x)
        request.y = float(y)
        request.theta = float(theta)
        request.name = name

        future = self.spawn_client.call_async(request)
        future.add_done_callback(
            partial(self._handle_spawn_done, requested_name=name, x=x, y=y, theta=theta)
        )

    def _handle_spawn_done(self, future, requested_name: str, x: float, y: float, theta: float) -> None:
        self.spawn_in_progress = False
        result = future.result()
        if result is None:
            self.get_logger().warn(f"Failed to spawn target {requested_name}")
            return

        self._remember_pose(result.name, x, y, theta)
        self._register_turtle(result.name, waiting_target=True)
        self.get_logger().info(f"Spawned waiting target {result.name}")

    def _register_turtle(self, name: str, waiting_target: bool, wait_for_pen: bool = False) -> None:
        if name in self.spawned_turtles:
            return

        self.spawned_turtles.add(name)
        self.cmd_publishers[name] = self.create_publisher(Twist, f"/{name}/cmd_vel", 10)
        subscription = self.create_subscription(
            Pose,
            f"/{name}/pose",
            partial(self._pose_callback, name=name),
            10,
        )
        self.pose_subscriptions.append(subscription)
        pen_future = self._turn_pen_off(name, wait=wait_for_pen)

        if waiting_target:
            self.waiting_targets.add(name)
            if not wait_for_pen and pen_future is not None:
                pen_future.add_done_callback(partial(self._confirm_target_pen_off, name=name))

    def _turn_pen_off(self, name: str, wait: bool = False):
        client = self.create_client(SetPen, f"/{name}/set_pen")
        self.pen_clients[name] = client
        if not client.wait_for_service(timeout_sec=1.0):
            self.get_logger().warn(f"Could not reach /{name}/set_pen")
            return None

        request = SetPen.Request()
        request.r = 255
        request.g = 255
        request.b = 255
        request.width = 1
        request.off = 1
        future = client.call_async(request)
        if wait:
            rclpy.spin_until_future_complete(self, future, timeout_sec=2.0)
            if future.result() is None:
                self.get_logger().warn(f"Failed to turn off pen for {name}")
        return future

    def _confirm_target_pen_off(self, future, name: str) -> None:
        if future.result() is None:
            self.get_logger().warn(f"Pen may still be on for {name}.")

    def _remember_pose(self, name: str, x: float, y: float, theta: float) -> None:
        pose = Pose()
        pose.x = float(x)
        pose.y = float(y)
        pose.theta = float(theta)
        self.poses[name] = pose

    def _clear_screen_sync(self) -> None:
        future = self.clear_client.call_async(Empty.Request())
        rclpy.spin_until_future_complete(self, future, timeout_sec=2.0)
        if future.result() is None:
            self.get_logger().warn("Could not clear startup pen marks.")

    def _wait_for_pose(self, name: str, timeout_sec: float = 2.0) -> None:
        end_time = self.get_clock().now().nanoseconds + int(timeout_sec * 1_000_000_000)
        while rclpy.ok() and name not in self.poses:
            if self.get_clock().now().nanoseconds >= end_time:
                self.get_logger().warn(f"Timed out waiting for pose from {name}")
                return
            rclpy.spin_once(self, timeout_sec=0.05)

    def _pose_callback(self, msg: Pose, name: str) -> None:
        self.poses[name] = msg

    def _control_loop(self) -> None:
        if not self.is_ready or self.MASTER_NAME not in self.poses:
            return

        self._keep_waiting_targets_still()

        if self.current_target_name is None or self.current_target_name not in self.waiting_targets:
            self._select_next_target()

        if self.current_target_name is None:
            self._publish_stop(self.MASTER_NAME)
            self._update_chain_following()
            return

        if self._is_touching(self.MASTER_NAME, self.current_target_name):
            self._catch_target(self.current_target_name)
            self.current_target_name = None
            self._select_next_target()

        if self.current_target_name is None:
            self._publish_stop(self.MASTER_NAME)
        elif self.current_target_name in self.poses:
            self._move_toward_point(self.MASTER_NAME, self._pose_xy(self.current_target_name))

        self._update_chain_following()

    def _keep_waiting_targets_still(self) -> None:
        for name in list(self.waiting_targets):
            self._publish_stop(name)

    def _nearest_waiting_target(self) -> Optional[str]:
        candidates = self._waiting_targets_by_distance()
        if not candidates:
            return None
        return candidates[0][1]

    def _select_next_target(self) -> None:
        self.current_target_name = self._nearest_waiting_target()
        if self.current_target_name is None:
            self.get_logger().info("No available target. Master turtle is waiting.")
            return

        distance = self._distance_between(self.MASTER_NAME, self.current_target_name)
        self.get_logger().info(f"Locked target {self.current_target_name} ({distance:.2f}).")

    def _waiting_targets_by_distance(self) -> List[Tuple[float, str]]:
        if self.MASTER_NAME not in self.poses:
            return []

        candidates = [
            (self._distance_between(self.MASTER_NAME, name), name)
            for name in self.waiting_targets
            if name in self.poses
        ]
        return sorted(candidates, key=lambda item: (item[0], item[1]))

    def _is_touching(self, first: str, second: str) -> bool:
        return self._distance_between(first, second) <= self.catch_radius

    def _catch_target(self, name: str) -> None:
        if name not in self.waiting_targets:
            return

        self.waiting_targets.remove(name)
        self.chain.append(name)
        self._publish_stop(name)
        self.get_logger().info(f"Caught {name}; chain length is now {len(self.chain)}")

    def _update_chain_following(self) -> None:
        leader_name = self.MASTER_NAME
        for follower_name in self.chain:
            leader_pose = self.poses.get(leader_name)
            if leader_pose is None or follower_name not in self.poses:
                leader_name = follower_name
                continue

            target_point = (
                leader_pose.x - self.follow_distance * math.cos(leader_pose.theta),
                leader_pose.y - self.follow_distance * math.sin(leader_pose.theta),
            )
            self._move_toward_point(follower_name, target_point, stop_radius=0.08)
            leader_name = follower_name

    def _move_toward_point(
        self,
        name: str,
        target: Tuple[float, float],
        stop_radius: float = 0.05,
    ) -> None:
        pose = self.poses.get(name)
        publisher = self.cmd_publishers.get(name)
        if pose is None or publisher is None:
            return

        dx = target[0] - pose.x
        dy = target[1] - pose.y
        distance = math.hypot(dx, dy)

        twist = Twist()
        if distance <= stop_radius:
            publisher.publish(twist)
            return

        target_angle = math.atan2(dy, dx)
        angle_error = normalize_angle(target_angle - pose.theta)

        twist.angular.z = clamp(4.0 * angle_error, -self.max_angular_speed, self.max_angular_speed)
        if abs(angle_error) < 1.2:
            twist.linear.x = clamp(1.6 * distance, 0.0, self.max_linear_speed)
        publisher.publish(twist)

    def _publish_stop(self, name: str) -> None:
        publisher = self.cmd_publishers.get(name)
        if publisher is not None:
            publisher.publish(Twist())

    def _distance_between(self, first: str, second: str) -> float:
        first_pose = self.poses[first]
        second_pose = self.poses[second]
        return math.hypot(first_pose.x - second_pose.x, first_pose.y - second_pose.y)

    def _pose_xy(self, name: str) -> Tuple[float, float]:
        pose = self.poses[name]
        return pose.x, pose.y

    def _random_spawn_pose(self, avoid_master_spawn: bool = False) -> Tuple[float, float, float]:
        for _ in range(50):
            x = random.uniform(self.world_min, self.world_max)
            y = random.uniform(self.world_min, self.world_max)
            if avoid_master_spawn and self._is_near_master_spawn(x, y):
                continue
            if self.MASTER_NAME not in self.poses:
                return x, y, random.uniform(-math.pi, math.pi)

            master_pose = self.poses[self.MASTER_NAME]
            if math.hypot(x - master_pose.x, y - master_pose.y) > 1.5:
                return x, y, random.uniform(-math.pi, math.pi)

        return (
            self.world_min,
            self.world_min,
            random.uniform(-math.pi, math.pi),
        )

    def _is_near_master_spawn(self, x: float, y: float) -> bool:
        return math.hypot(x - self.master_spawn_x, y - self.master_spawn_y) < 2.0

    def _next_target_name(self) -> str:
        self.spawn_index += 1
        return f"target_{self.spawn_index}"


def main(args=None) -> None:
    rclpy.init(args=args)
    node = CatchTurtleNode()
    try:
        node.setup_game()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
