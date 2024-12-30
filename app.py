# app.py
from flask import Flask, request, jsonify
import os
from dotenv import load_dotenv
from google.generativeai import GenerativeModel
from dataclasses import dataclass
from typing import List, Optional
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

@dataclass
class Node:
    id: str
    label: Optional[str] = None

@dataclass
class Edge:
    source: str
    target: str
    label: Optional[str] = None

@dataclass
class Subgraph:
    title: str
    nodes: List[Node]

@dataclass
class MermaidDiagram:
    nodes: List[Node]
    title: Optional[str] = None

def generate_mermaid(diagram: MermaidDiagram) -> str:
    def node_to_mermaid(node):
        if isinstance(node, Node):
            return f'{node.id}["{node.label or node.id}"]'
        elif isinstance(node, Edge):
            return f'{node.source} -->{f"|{node.label}|" if node.label else ""} {node.target}'
        elif isinstance(node, Subgraph):
            inner_content = "\n".join([node_to_mermaid(n) for n in node.nodes])
            return f"subgraph {node.title}\n{inner_content}\nend"
    
    content = "\n".join([node_to_mermaid(node) for node in diagram.nodes])
    return f"flowchart TD\n{content}"  # Remove title line

def parse_llm_response(text: str, title: str) -> MermaidDiagram:
    lines = text.strip().split('\n')
    nodes = []
    edges = []
    
    # Process only lines containing nodes or edges
    for line in lines:
        if '-->' in line:
            parts = line.split('-->')
            source = parts[0].strip()
            target = parts[1].strip()
            edges.append(Edge(source=source, target=target))
        elif '[' in line and not line.startswith('flowchart'):
            node_id = line.split('[')[0].strip()
            label = line.split('[')[1].split(']')[0].strip('"')
            nodes.append(Node(id=node_id, label=label))

    return MermaidDiagram(nodes=nodes + edges, title=title)



model = GenerativeModel('gemini-pro')
sys_prompt = """
You are an instructor that explains things visually. You have the ability to produce diagrams via mermaid.js code.
You should always be trying to explain things visually with a mermaid.js diagram.
Generate minimal and clean mermaid.js code that accurately represents the concept or process being explained. Avoid adding comments, extra lines, or unnecessary descriptive lines in the code.
Ensure all nodes, connections, and labels are logically connected, simple to interpret, and visually clear. Focus on presenting the structure, not excessive details.
The diagram should start directly with 'flowchart TD' followed by the relevant nodes and edges. There should be no introductory lines or additional text.
dont use END in code .inplace of thses use Exit
 
example:
flowchart TD
A["Rain"]
B["Evaporation"]
C["Condensation"]
D["Water"]
A --> B
B --> C
C --> D
"""


@app.route('/generate', methods=['POST'])
def generate_diagram():
    try:
        data = request.get_json()
        user_input = data.get('input', '')
        
        if not GOOGLE_API_KEY:
            return jsonify({'error': 'API key not found'}), 500
        
        chat = model.start_chat(history=[])
        response = chat.send_message(
            f"{sys_prompt}\nCreate a diagram for: {user_input}"
        )
        
        if response.text:
            # Parse the response and generate Mermaid code
            diagram = parse_llm_response(response.text, user_input)
            mermaid_code = generate_mermaid(diagram)
            return jsonify({
                'code': mermaid_code,
                'rawResponse': response.text
            })
        
        return jsonify({'error': 'No response generated'}), 500
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

