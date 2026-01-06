import pyautogui
import time

print("Pon el mouse en la ESQUINA SUPERIOR IZQUIERDA del área de turnos en 5s...")
time.sleep(5)
x1, y1 = pyautogui.position()
print("Sup-izq:", x1, y1)

print("Ahora pon el mouse en la ESQUINA INFERIOR DERECHA del área de turnos en 5s...")
time.sleep(5)
x2, y2 = pyautogui.position()
print("Inf-der:", x2, y2)

print("BBOX =", (x1, y1, x2, y2))
