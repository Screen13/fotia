# FOTIA

Aplicación que te deja analizar tus fotos a lo bestia y luego puedes buscar fotos por objetos que salen en ellas o por gente. Todo offline, como RMS manda.

Busca en la carpeta que le digas, detecta qué hay en cada foto (personas, coches, perros...) y reconoce caras para agruparlas por persona. Después puedes buscar combinando etiquetas y nombres. Como las clouds de los moviles, pero sin mandarle tus fotos a Johnny el usurero.

## Me lo quiero instalar

Pues necesitas **Python 3.11+** (con tkinter).

```bash
# Clona esto
git clone https://github.com/Screen13/fotia.git
cd fotia

# Crea un entorno virtual (porque si no python es un merder), y te instalas las dependencias.
python3 -m venv env
source env/bin/activate        # En Windows: env\Scripts\activate
pip install -r requirements.txt
```

### Si tienes un Mac...

...y te da un error de face_recognition

```bash
pip install setuptools<81
pip install git+https://github.com/ageitgey/face_recognition_models
```

También mira a ver si tienes `python-tk` instalado

```bash
brew install python-tk@3.12
```

### Si tienes Windows...

Ponte [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) con "Desktop development with C++" para poder compilar `dlib`.

### Y si eres un ser de luz y usas Linux...

```bash
sudo apt install cmake python3-tk
```

## ¿Como se usa?

```bash
source env/bin/activate        # En Windows: env\Scripts\activate
python app.py
```

1. En **Buscar**, pues eso. Puedes buscar.
2. En **Análisis**, selecciona una carpeta con fotos y dale a que analice.
3. En **Reconocimiento**, ves mirando las caras que ha encontrado y ponles nombre.


## Stack

- **UI**: CustomTkinter
- **Detección de objetos**: YOLOv8n (ultralytics)
- **Reconocimiento facial**: face_recognition (dlib)
- **Datos**: CSV + JSON (sin base de datos externa)

## ¿Por qué el icono es un mapache?

Porque le gustan a Ada y a mi también.
