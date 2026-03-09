# Crear política
cd C:\space_r1\IsaacLab

```bash 
isaablab.bat --new
```
Pasos a seguir de la instalacion:
(Selecciona las opciones con SPACE y confirma con ENTER)
- External
- Path del proyecto C:\space_r1
- Nombre de la política
- Single Agent
- rsl_rl y skrl
- AMP y PPO

### Siguiente paso:
- Abrir la carpeta de la política:
```bash
cd C:\space_r1\<nombre de la politica (proyecto)>
```
## Configuraciones de entrenamiento politica
Las carpetas que contienen la informacion sobre los rewards y penaltys que se le aplican en el entrenamiento estan en la ruta:
```bash
cd C:\space_r1\r1_standing\source\r1_standing\r1_standing\tasks\direct\r1_standing
```
### Organizacion de Archivos
- r1_standing_env_cfg.py:
- - Codigo donde colocamos (rewards y penaltys) en valores simples
- r1_standing_env.py:
- -  Codigo que define las reglas que aplican los rewards y las penaltys

## Configuracion pesos de entrenamiento
```bash
cd C:\space_r1\r1_standing\source\r1_standing\r1_standing\tasks\direct\r1_standing\agents
```

# Abrir el entorno inicial
- Abrir CMD en modo administrador 
- cd C:\space_r1 - (Ubicación donde guardamos IsaabLab y nuestras politicas por separado)
- Ejecutar entorno de conda
```bash
conda activate env_isaaclab
```




