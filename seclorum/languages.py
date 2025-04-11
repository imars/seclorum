# seclorum/languages.py
LANGUAGE_CONFIG = {
    "python": {
        "code_prompt": "Generate Python code to {description}. Return only the raw, executable Python code without Markdown, comments, or explanations.",
        "test_prompt": "Generate a Python unit test for this code:\n{code}\nReturn only the raw, executable Python test code without Markdown, comments, or explanations.",
        "debug_prompt": "Fix this Python code that failed with error:\n{error}\nOriginal code:\n{code}\nReturn only the corrected Python code without Markdown or explanations.",
        "comment_prefix": "#",
        "test_framework": "unittest",
        "file_extension": ".py",
        "execute_cmd": ["python", "-B"]
    },
    "javascript": {
        "code_prompt": (
            "Generate JavaScript code to {description}. "
            "Return only the raw, executable JavaScript code suitable for Node.js (e.g., use 'require' for modules). "
            "If the description mentions 3D, Three.js, or graphics, assume 'three' is available via 'require(\"three\")' "
            "and do not include CDN links or <script> tags unless explicitly requested."
        ),
        "test_prompt": "Generate a JavaScript unit test (using Jest syntax) for this code:\n{code}\nReturn only the raw, executable test code without Markdown, comments, or explanations.",
        "debug_prompt": "Fix this JavaScript code that failed with error:\n{error}\nOriginal code:\n{code}\nReturn only the corrected JavaScript code without Markdown or explanations.",
        "comment_prefix": "//",
        "test_framework": "jest",
        "file_extension": ".js",
        "execute_cmd": ["node"]
    },
    "css": {
        "code_prompt": "Generate CSS code to {description}. Return only the raw, executable CSS code without Markdown, comments, or explanations.",
        "test_prompt": None,
        "debug_prompt": "Fix this CSS code that failed with error:\n{error}\nOriginal code:\n{code}\nReturn only the corrected CSS code without Markdown or explanations.",
        "comment_prefix": "/*",
        "test_framework": None,
        "file_extension": ".css",
        "execute_cmd": None
    },
    "html": {
        "code_prompt": "Generate HTML code to {description}. Return only the raw, executable HTML code without Markdown, comments, or explanations.",
        "test_prompt": None,
        "debug_prompt": "Fix this HTML code that failed with error:\n{error}\nOriginal code:\n{code}\nReturn only the corrected HTML code without Markdown or explanations.",
        "comment_prefix": "<!--",
        "test_framework": None,
        "file_extension": ".html",
        "execute_cmd": None
    },
    "cpp": {
        "code_prompt": "Generate C++ code to {description}. Return only the raw, executable C++ code without Markdown, comments, or explanations.",
        "test_prompt": "Generate a C++ unit test (using Google Test syntax) for this code:\n{code}\nReturn only the raw, executable test code without Markdown, comments, or explanations.",
        "debug_prompt": "Fix this C++ code that failed with error:\n{error}\nOriginal code:\n{code}\nReturn only the corrected C++ code without Markdown or explanations.",
        "comment_prefix": "//",
        "test_framework": "gtest",
        "file_extension": ".cpp",
        "execute_cmd": ["g++", "-o", "temp_task", "-lgtest", "-lgtest_main", "-pthread"]
    }
}
