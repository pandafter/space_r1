"""R1 Locomotion — Terminal Manual Control.

Architecture:
  MAIN THREAD   → Isaac Sim simulation loop (env.step, rendering, physics)
  BG THREAD     → Terminal input: menu, WASD keys, coordinate entry
  BRIDGE        → SimController with queue.Queue (thread-safe command passing)

Isaac Sim REQUIRES the main thread for rendering. Previous version put sim in a
background thread, which caused the freeze.
"""

# ── Phase 1: Pre-Isaac-Sim imports ──────────────────────────────────── #

import argparse
import glob
import importlib
import os
import threading
import queue
import msvcrt  # Windows native — non-blocking key reading

from isaaclab.app import AppLauncher

# ── Argparse ────────────────────────────────────────────────────────── #

parser = argparse.ArgumentParser(description="R1 Locomotion — Terminal Manual Control")
parser.add_argument("--task", type=str, default="R1-Locomotion-Direct-v0")
parser.add_argument("--checkpoint", type=str, default=None, help="Path to checkpoint (.pt)")
parser.add_argument("--step", type=float, default=0.5, help="Step size per WASD key press (meters)")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

# ── Launch Isaac Sim ────────────────────────────────────────────────── #

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

# ── Phase 2: Post-Isaac-Sim imports ─────────────────────────────────── #

import time  # noqa: E402
import torch  # noqa: E402
import gymnasium as gym  # noqa: E402

from rsl_rl.runners import OnPolicyRunner  # noqa: E402
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper  # noqa: E402
from isaaclab_tasks.utils import parse_env_cfg  # noqa: E402

import isaaclab_tasks  # noqa: F401, E402
import r1_locomotion.tasks  # noqa: F401, E402


# ====================================================================== #
# Helpers
# ====================================================================== #

def find_latest_checkpoint() -> str | None:
    """Auto-discover the most recent checkpoint."""
    search_roots = [
        os.path.join("IsaacLab", "logs", "rsl_rl"),
        os.path.join("logs", "rsl_rl"),
    ]
    all_checkpoints = []
    for root in search_roots:
        pattern = os.path.join(root, "r1_locomotion*", "*", "model_*.pt")
        all_checkpoints.extend(glob.glob(pattern))
    if all_checkpoints:
        all_checkpoints.sort(key=os.path.getmtime)
        return all_checkpoints[-1]
    return None


# ====================================================================== #
# SimController — thread-safe bridge
# ====================================================================== #

class SimController:
    """Thread-safe bridge between input thread and simulation thread."""

    def __init__(self, device):
        self.device = device
        self._cmd_queue = queue.Queue()
        self.running = True
        # Latest robot state (written by main/sim thread, read by input thread)
        self.robot_xy = [0.0, 0.0]
        self.target_xy = [0.0, 0.0]
        self.distance = 0.0
        self._lock = threading.Lock()
        # Reset flag — simple boolean, no queue drain issues
        self._needs_reset = False

    def send_target(self, x: float, y: float):
        """Send absolute target position (from input thread)."""
        self._cmd_queue.put(("set", x, y))

    def send_delta(self, dx: float, dy: float):
        """Send incremental target delta (from input thread)."""
        self._cmd_queue.put(("delta", dx, dy))

    def send_reset(self):
        """Request environment reset (flag-based, not queue)."""
        self._needs_reset = True

    def send_stop(self):
        """Set target = robot position (stop walking)."""
        self._cmd_queue.put(("stop",))

    def process_commands(self, raw_env):
        """Process all pending commands (called from main/sim thread)."""
        while not self._cmd_queue.empty():
            try:
                cmd = self._cmd_queue.get_nowait()
                if cmd[0] == "set":
                    raw_env.target_pos_w[0, 0] = cmd[1]
                    raw_env.target_pos_w[0, 1] = cmd[2]
                elif cmd[0] == "delta":
                    raw_env.target_pos_w[0, 0] += cmd[1]
                    raw_env.target_pos_w[0, 1] += cmd[2]
                elif cmd[0] == "stop":
                    robot_xy = raw_env.robot.data.root_pos_w[0, :2]
                    raw_env.target_pos_w[0] = robot_xy.clone()
            except queue.Empty:
                break

    def check_reset(self):
        """Check and clear reset flag (called from main/sim thread)."""
        if self._needs_reset:
            self._needs_reset = False
            return True
        return False

    def update_state(self, raw_env):
        """Update cached state for display (called from main/sim thread)."""
        with self._lock:
            rxy = raw_env.robot.data.root_pos_w[0, :2]
            txy = raw_env.target_pos_w[0]
            self.robot_xy = [rxy[0].item(), rxy[1].item()]
            self.target_xy = [txy[0].item(), txy[1].item()]
            self.distance = torch.norm(txy - rxy).item()

    def get_state(self):
        """Get latest state snapshot (from input thread)."""
        with self._lock:
            return self.robot_xy.copy(), self.target_xy.copy(), self.distance


# ====================================================================== #
# Input Thread (BACKGROUND) — Menu + WASD + Coordinates
# ====================================================================== #

def print_status(ctrl: SimController):
    """Print current robot and target positions."""
    rxy, txy, dist = ctrl.get_state()
    print(f"\n  Robot:  ({rxy[0]:+.2f}, {rxy[1]:+.2f})")
    print(f"  Target: ({txy[0]:+.2f}, {txy[1]:+.2f})")
    print(f"  Dist:   {dist:.2f} m")


def mode_coordinate(ctrl: SimController):
    """Mode 1: Type incremental coordinates relative to robot."""
    print("\n  ── MODO COORDENADA ──")
    print("  Escribe 'dx dy' para mover el target desde la posicion actual del robot")
    print("  Ejemplo: '1.0 0.5' mueve +1m en X, +0.5m en Y")
    print("  'abs x y' para coordenada absoluta")
    print("  'q' para volver al menu\n")

    while ctrl.running:
        try:
            cmd = input("  coord> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not cmd or cmd.lower() == "q":
            break

        if cmd.lower() == "p":
            print_status(ctrl)
            continue

        if cmd.lower() == "stop":
            ctrl.send_stop()
            print("  -> Target = posicion del robot (frenando)")
            continue

        try:
            parts = cmd.split()
            if parts[0].lower() == "abs" and len(parts) >= 3:
                x, y = float(parts[1]), float(parts[2])
                ctrl.send_target(x, y)
                print(f"  -> Target absoluto: ({x:+.2f}, {y:+.2f})")
            elif len(parts) >= 2:
                dx, dy = float(parts[0]), float(parts[1])
                rxy, _, _ = ctrl.get_state()
                new_x = rxy[0] + dx
                new_y = rxy[1] + dy
                ctrl.send_target(new_x, new_y)
                print(f"  -> Robot ({rxy[0]:+.2f}, {rxy[1]:+.2f}) + ({dx:+.2f}, {dy:+.2f}) = Target ({new_x:+.2f}, {new_y:+.2f})")
            else:
                print("  -> Formato: dx dy  |  abs x y  |  stop  |  p  |  q")
        except ValueError:
            print("  -> Numeros invalidos. Ejemplo: 1.0 0.5")


def mode_keyboard(ctrl: SimController, step_size: float):
    """Mode 2: Real-time WASD control via msvcrt (terminal key reading)."""
    print("\n  ── MODO TECLADO ──")
    print(f"  Paso por tecla: {step_size} m")
    print("  W = +X (adelante)    S = -X (atras)")
    print("  A = -Y (izquierda)   D = +Y (derecha)")
    print("  P = posicion    0 = stop (target=robot)")
    print("  Q = volver al menu\n")

    while ctrl.running:
        if msvcrt.kbhit():
            ch = msvcrt.getwch().lower()

            if ch == "q":
                break
            elif ch == "w":
                ctrl.send_delta(step_size, 0.0)
                rxy, txy, dist = ctrl.get_state()
                print(f"\r  [W +X] Target: ({txy[0]+step_size:+.2f}, {txy[1]:+.2f}) | Dist: {dist:.2f}m   ", end="", flush=True)
            elif ch == "s":
                ctrl.send_delta(-step_size, 0.0)
                rxy, txy, dist = ctrl.get_state()
                print(f"\r  [S -X] Target: ({txy[0]-step_size:+.2f}, {txy[1]:+.2f}) | Dist: {dist:.2f}m   ", end="", flush=True)
            elif ch == "a":
                ctrl.send_delta(0.0, -step_size)
                rxy, txy, dist = ctrl.get_state()
                print(f"\r  [A -Y] Target: ({txy[0]:+.2f}, {txy[1]-step_size:+.2f}) | Dist: {dist:.2f}m   ", end="", flush=True)
            elif ch == "d":
                ctrl.send_delta(0.0, step_size)
                rxy, txy, dist = ctrl.get_state()
                print(f"\r  [D +Y] Target: ({txy[0]:+.2f}, {txy[1]+step_size:+.2f}) | Dist: {dist:.2f}m   ", end="", flush=True)
            elif ch == "p":
                print_status(ctrl)
            elif ch == "0":
                ctrl.send_stop()
                print("\n  -> Stop: target = posicion del robot")
        else:
            time.sleep(0.02)


def input_thread_fn(ctrl: SimController, step_size: float):
    """Background thread: handles all user input via terminal.

    Runs in a daemon thread so it auto-exits when main thread finishes.
    """
    # Wait for main thread to start the sim loop and render the first frames
    time.sleep(3.0)

    print("\n" + "=" * 55)
    print("  R1 LOCOMOTION -- CONTROL MANUAL POR TERMINAL")
    print("=" * 55)

    while ctrl.running:
        print("\n  ── MENU PRINCIPAL ──")
        print("  1. Coordenada (escribir dx dy)")
        print("  2. Teclado WASD (tiempo real)")
        print("  3. Ver posicion")
        print("  4. Resetear environment")
        print("  5. Salir")

        try:
            choice = input("\n  opcion> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if choice == "1":
            mode_coordinate(ctrl)
        elif choice == "2":
            mode_keyboard(ctrl, step_size)
        elif choice == "3":
            print_status(ctrl)
        elif choice == "4":
            ctrl.send_reset()
            print("  -> Environment reseteado")
        elif choice == "5":
            break
        else:
            print("  -> Opcion invalida (1-5)")

    # Signal main thread to stop
    ctrl.running = False


# ====================================================================== #
# Main — Simulation loop on MAIN THREAD (required by Isaac Sim)
# ====================================================================== #

def main():
    # ── Resolve checkpoint ──────────────────────────────────────────── #
    if args_cli.checkpoint is not None:
        checkpoint_path = args_cli.checkpoint
    else:
        checkpoint_path = find_latest_checkpoint()
        if checkpoint_path is None:
            print("[ERROR] No checkpoint found. Provide --checkpoint path.")
            return

    print(f"[INFO] Using checkpoint: {checkpoint_path}")

    # ── Environment (force num_envs=1) ──────────────────────────────── #
    env_cfg = parse_env_cfg(args_cli.task, device=args_cli.device, num_envs=1)
    env_cfg.scene.num_envs = 1
    env = gym.make(args_cli.task, cfg=env_cfg)
    env = RslRlVecEnvWrapper(env)

    # ── Load agent config + checkpoint ──────────────────────────────── #
    gym_spec = gym.spec(args_cli.task)
    agent_cfg_entry = gym_spec.kwargs.get("rsl_rl_cfg_entry_point")
    module_path, class_name = agent_cfg_entry.rsplit(":", 1)
    module = importlib.import_module(module_path)
    agent_cfg = getattr(module, class_name)()

    runner = OnPolicyRunner(env, agent_cfg.to_dict(), log_dir=None, device=env_cfg.sim.device)
    runner.load(checkpoint_path)
    policy = runner.get_inference_policy(device=env.unwrapped.device)

    raw_env = env.unwrapped

    # ── Controller (thread-safe bridge) ─────────────────────────────── #
    ctrl = SimController(device=raw_env.device)

    # ── Start input in BACKGROUND thread ────────────────────────────── #
    input_t = threading.Thread(
        target=input_thread_fn,
        args=(ctrl, args_cli.step),
        daemon=True,  # auto-exits when main thread ends
    )
    input_t.start()

    # ── Simulation loop on MAIN THREAD ──────────────────────────────── #
    # Isaac Sim rendering/physics MUST run on main thread to avoid freeze
    raw_env.cfg.target_resample_on_arrival = False
    obs = env.get_observations()
    step_count = 0

    print("[INFO] Simulation running on main thread. Menu will appear in ~3 seconds...")

    while ctrl.running and simulation_app.is_running():
        with torch.inference_mode():
            # Process pending target/delta/stop commands from input thread
            ctrl.process_commands(raw_env)

            # Handle environment reset (flag-based, not queue)
            if ctrl.check_reset():
                env.reset()
                obs = env.get_observations()
                raw_env.cfg.target_resample_on_arrival = False
                continue

            # Policy inference + simulation step
            actions = policy(obs)
            obs, _, dones, _ = env.step(actions)
            policy.reset(dones)

        # Update state cache for input thread display (every 30 steps)
        step_count += 1
        if step_count % 30 == 0:
            ctrl.update_state(raw_env)

    # ── Cleanup ─────────────────────────────────────────────────────── #
    ctrl.running = False
    env.close()


if __name__ == "__main__":
    main()
    simulation_app.close()
