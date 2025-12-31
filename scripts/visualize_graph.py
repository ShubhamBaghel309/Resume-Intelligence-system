"""
Visualize the LangGraph workflow for the Resume Intelligence Agent
"""
import sys
sys.path.append("d:/GEN AI internship work/Resume Intelligence System")

from app.workflows.intelligent_agent import create_intelligent_agent

# Create the compiled graph
graph = create_intelligent_agent()

# Method 1: Get Mermaid diagram (text-based)
print("=" * 80)
print("LANGGRAPH VISUALIZATION - MERMAID FORMAT")
print("=" * 80)
print("\nYou can copy this and paste it into:")
print("- https://mermaid.live/ (online Mermaid editor)")
print("- GitHub markdown files")
print("- VS Code with Mermaid extension")
print("\n" + "=" * 80 + "\n")

try:
    # Get the Mermaid representation
    mermaid_code = graph.get_graph().draw_mermaid()
    print(mermaid_code)
    
    # Save to file
    with open("agent_graph.mmd", "w", encoding="utf-8") as f:
        f.write(mermaid_code)
    
    print("\n" + "=" * 80)
    print("✅ Mermaid diagram saved to: agent_graph.mmd")
    print("=" * 80)
    
except Exception as e:
    print(f"❌ Error generating Mermaid: {e}")

# Method 2: Generate PNG image (requires graphviz)
print("\n\n" + "=" * 80)
print("GENERATING PNG IMAGE")
print("=" * 80)

try:
    from IPython.display import Image
    
    # Generate PNG
    png_data = graph.get_graph().draw_mermaid_png()
    
    # Save to file
    with open("agent_graph.png", "wb") as f:
        f.write(png_data)
    
    print("✅ PNG image saved to: agent_graph.png")
    print("   Open this file to see the visual graph!")
    
except ImportError:
    print("⚠️  PNG generation requires: pip install pygraphviz")
    print("   For now, use the Mermaid code above at https://mermaid.live/")
except Exception as e:
    print(f"⚠️  PNG generation failed: {e}")
    print("   Use the Mermaid code above instead")

print("\n" + "=" * 80)
print("VISUALIZATION COMPLETE")
print("=" * 80)
print("\nOptions to view:")
print("1. Open agent_graph.png (if generated)")
print("2. Copy agent_graph.mmd content to https://mermaid.live/")
print("3. View agent_graph.mmd in VS Code with Mermaid extension")
