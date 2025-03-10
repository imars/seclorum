from setuptools import setup, find_packages

setup(
    name="seclorum",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pydantic",
        "flask",
        "flask-socketio",
        "gitpython",
        "click",
        "ollama",  # Assuming Ollama has a Python package
    ],
    entry_points={
        "console_scripts": [
            "seclorum=seclorum.cli.commands:main",
        ]
    },
    author="imars",
    description="An intelligent development environment with AI agents",
    url="https://github.com/imars/seclorum",
)
