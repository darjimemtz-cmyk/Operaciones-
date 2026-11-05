import os

# 1. Ajustar app.py a 7 días rodantes
with open("app.py", "r", encoding="utf-8") as f:
    c = f.read()

c = c.replace("fechas_8dias", "fechas_7dias")
c = c.replace("['?']*8", "['?']*7")
c = c.replace("res_8d", "res_7d")
c = c.replace("usadas_8d", "usadas_7d")
c = c.replace("usadas_8dias", "usadas_7d")

with open("app.py", "w", encoding="utf-8") as f:
    f.write(c)
print("✅ app.py: Ventana rodante configurada a 7 días.")

# 2. Ajustar modal de sobregiros en templates/horas_dot.html
ruta_html = "templates/horas_dot.html" if os.path.exists("templates/horas_dot.html") else "horas_dot.html"
with open(ruta_html, "r", encoding="utf-8") as f:
    h = f.read()

h = h.replace("ventana rodante de 8 días", "ventana rodante de 7 días")
h = h.replace("ventana.length > 8", "ventana.length > 7")
h = h.replace("acum8", "acum7")

with open(ruta_html, "w", encoding="utf-8") as f:
    f.write(h)
print("✅ horas_dot.html: Modal ajustado a 7 días.")
