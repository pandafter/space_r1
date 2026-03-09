[INFO]: Time taken for simulation start : 1.533806 seconds
Creating window for environment.
ManagerLiveVisualizer cannot be created for manager: action_manager, Manager does not exist
ManagerLiveVisualizer cannot be created for manager: observation_manager, Manager does not exist
[INFO]: Completed setting up the environment...
--------------------------------------------------------------------------------
Resolved observation sets:
         actor :  ['policy']
         critic :  ['policy']
--------------------------------------------------------------------------------
Actor Model: MLPModel(
  (obs_normalizer): Identity()
  (mlp): MLP(
    (0): Linear(in_features=97, out_features=256, bias=True)
    (1): ELU(alpha=1.0)
    (2): Linear(in_features=256, out_features=128, bias=True)
    (3): ELU(alpha=1.0)
    (4): Linear(in_features=128, out_features=64, bias=True)
    (5): ELU(alpha=1.0)
    (6): Linear(in_features=64, out_features=26, bias=True)
  )
)
Critic Model: MLPModel(
  (obs_normalizer): Identity()
  (mlp): MLP(
    (0): Linear(in_features=97, out_features=256, bias=True)
    (1): ELU(alpha=1.0)
    (2): Linear(in_features=256, out_features=128, bias=True)
    (3): ELU(alpha=1.0)
    (4): Linear(in_features=128, out_features=64, bias=True)
    (5): ELU(alpha=1.0)
    (6): Linear(in_features=64, out_features=1, bias=True)
  )
)

=======================================================
  R1 LOCOMOTION -- CONTROL MANUAL POR TERMINAL
=======================================================

  ── MENU PRINCIPAL ──
  1. Coordenada (escribir dx dy)
  2. Teclado WASD (tiempo real)
  3. Ver posicion
  4. Resetear environment
  5. Salir

  opcion> 2

  ── MODO TECLADO ──
  Paso por tecla: 0.5 m
  W = +X (adelante)    S = -X (atras)
  A = -Y (izquierda)   D = +Y (derecha)
  P = posicion    0 = stop (target=robot)
  Q = volver al menu

  [W +X] Target: (+1.90, -2.55) | Dist: 2.91m   ^C
(env_isaaclab) C:\space_r1>