#!/usr/bin/env bash
set -eo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="${ROOT_DIR}/ros2_ws"
ROS_SETUP="/opt/ros/humble/setup.bash"
COLCON_BIN="/usr/bin/colcon"
SYSTEM_PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

if [[ "${EUID}" -eq 0 ]]; then
  echo "Do not run this script with sudo/root; it can create root-owned build files." >&2
  echo "Run it as the normal user instead: bash ${BASH_SOURCE[0]}" >&2
  exit 1
fi

export PATH="${SYSTEM_PATH}:${PATH}"
export PYTHONNOUSERSITE=1
unset PYTHONHOME
unset CONDA_PREFIX CONDA_DEFAULT_ENV CONDA_PROMPT_MODIFIER

if [[ ! -f "${ROS_SETUP}" ]]; then
  echo "ROS2 Humble was not found at ${ROS_SETUP}" >&2
  exit 1
fi

source "${ROS_SETUP}"
set -u

cd "${WORKSPACE_DIR}"

OWNER="$(id -un)"
GROUP="$(id -gn)"
for dir in build install log; do
  mkdir -p "${WORKSPACE_DIR}/${dir}"
  if find "${WORKSPACE_DIR}/${dir}" ! -user "${OWNER}" -print -quit | read -r _; then
    echo "Found build files not owned by ${OWNER}; fixing workspace permissions..." >&2
    if command -v sudo >/dev/null 2>&1; then
      sudo chown -R "${OWNER}:${GROUP}" \
        "${WORKSPACE_DIR}/build" \
        "${WORKSPACE_DIR}/install" \
        "${WORKSPACE_DIR}/log"
      break
    fi
    echo "sudo is not available. Run this once, then retry:" >&2
    echo "  sudo chown -R ${OWNER}:${GROUP} ${WORKSPACE_DIR}/build ${WORKSPACE_DIR}/install ${WORKSPACE_DIR}/log" >&2
    exit 1
  fi
  if [[ ! -w "${WORKSPACE_DIR}/${dir}" ]]; then
    echo "${WORKSPACE_DIR}/${dir} is not writable. Run:" >&2
    echo "  sudo chown -R ${OWNER}:${GROUP} ${WORKSPACE_DIR}/build ${WORKSPACE_DIR}/install ${WORKSPACE_DIR}/log" >&2
    exit 1
  fi
done

"${COLCON_BIN}" build --packages-select catch_turtle_all
set +u
source "${WORKSPACE_DIR}/install/setup.bash"
set -u

ros2 launch catch_turtle_all catch_turtle.launch.py
