"""Simple test to verify FastEmbed works with our setup."""
import sys

print("Python version:", sys.version)
print("Attempting to import fastembed...")

try:
    from fastembed import TextEmbedding
    print("✓ FastEmbed imported successfully")

    print("\nInitializing TextEmbedding model...")
    model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    print("✓ Model initialized successfully")

    print("\nTesting embedding generation...")
    test_texts = ["Hello world", "This is a test"]
    embeddings = list(model.embed(test_texts))
    print(f"✓ Generated {len(embeddings)} embeddings")
    print(f"  Embedding dimension: {len(embeddings[0])}")
    print(f"  First few values: {embeddings[0][:5]}")

    print("\n✓✓✓ All tests passed! FastEmbed is working correctly.")

except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
