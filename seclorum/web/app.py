from flask import Flask, render_template
from seclorum.core.filesystem import FileSystemManager

app = Flask(__name__)
fs_manager = FileSystemManager("./project")

@app.route("/")
def index():
    files = [f.name for f in fs_manager.path.iterdir() if f.is_file()]
    return render_template("index.html", files=files)

@app.route("/chat")
def chat():
    return render_template("chat.html")
