import ast, pathlib 
p=pathlib.Path('app/main.py') 
src=p.read_text(encoding='utf-8') 
tree=ast.parse(src) 
lines=src.splitlines() 
class V(ast.NodeVisitor): 
    def __init__(self): self.stack=[] 
    def visit_FunctionDef(self,n): self.stack.append(n.name); self.generic_visit(n); self.stack.pop() 
    def visit_AsyncFunctionDef(self,n): self.stack.append(n.name); self.generic_visit(n); self.stack.pop() 
    def visit_Try(self,n): 
        for h in n.handlers: 
            ex='any' if h.type is None else getattr(h.type,'id',type(h.type).__name__) 
