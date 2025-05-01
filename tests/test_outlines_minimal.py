import outlines
from outlines.models import LlamaCpp
from seclorum.models.managers.outlines import OutlinesModelManager

def test_outlines_minimal():
    manager = None
    try:
        manager = OutlinesModelManager(model_name="mistral:latest")
        model = LlamaCpp(model=manager.llama)  # Use manager's Llama instance
        generator = outlines.generate.text(model)
        result = generator("Hello, world!", max_tokens=10)
        print(result)
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        # No need to close manager or Llama explicitly; handled by __del__
        pass

if __name__ == "__main__":
    test_outlines_minimal()
