"""Compile a bounded table program to Wasm without executing Python source."""

import ast
from importlib.metadata import version
from struct import pack

WIDTH = 6
LIMIT_ROWS = 48
ENGINE = '51.0.0'


class Refused(ValueError):
    pass


BIN = {ast.Add:'add',ast.Sub:'sub',ast.Mult:'mul',ast.FloorDiv:'div_s',ast.Mod:'rem_s',
       ast.BitAnd:'and',ast.BitOr:'or',ast.BitXor:'xor'}
CMP = {ast.Lt:'lt_s',ast.LtE:'le_s',ast.Gt:'gt_s',ast.GtE:'ge_s',ast.Eq:'eq',ast.NotEq:'ne'}


class Compiler:
    def __init__(self, source,revision):
        if not isinstance(source,str) or not 1<=len(source.encode())<=2400:
            raise Refused('PROGRAM_SIZE')
        try:
            tree=ast.parse(source)
        except (SyntaxError,ValueError) as error:
            raise Refused('SYNTAX') from error
        nodes=list(ast.walk(tree))
        if len(nodes)>240 or len(tree.body)!=1 or type(tree.body[0]) is not ast.FunctionDef:
            raise Refused('PROGRAM_SHAPE')
        function=tree.body[0]
        args=function.args
        if (function.name!='choose' or function.decorator_list or function.returns or
                [x.arg for x in args.args]!=['n','r'] or any(x.annotation for x in args.args) or
                args.vararg or args.kwarg or args.defaults or args.kwonlyargs or args.posonlyargs):
            raise Refused('SIGNATURE')
        names={node.id for node in nodes if isinstance(node,ast.Name) and isinstance(node.ctx,ast.Store)}
        if len(names)>20 or names & {'n','r','v','pop','range'} or any(not k.isascii() or not k.isidentifier() for k in names):
            raise Refused('LOCALS')
        self.locals={name:f'$l{index}' for index,name in enumerate(sorted(names))}
        self.variables={'n':'$n','r':'$r',**self.locals}
        self.counter=0
        if revision not in (1,2):
            raise Refused('COMPILER_REVISION')
        self.revision=revision
        self.body=self.block(function.body)

    def value(self,node):
        kind=type(node)
        if kind is ast.Constant and type(node.value) is int and -(2**30)<=node.value<=2**30:
            return f'i32.const {node.value}'
        if kind is ast.Name and node.id in self.variables:
            return 'local.get '+self.variables[node.id]
        if kind is ast.BinOp and type(node.op) in BIN:
            return f'{self.value(node.left)} {self.value(node.right)} i32.{BIN[type(node.op)]}'
        if kind is ast.Compare and len(node.ops)==1 and type(node.ops[0]) in CMP:
            return f'{self.value(node.left)} {self.value(node.comparators[0])} i32.{CMP[type(node.ops[0])]}'
        if kind is ast.UnaryOp and type(node.op) is ast.USub:
            return 'i32.const 0 '+self.value(node.operand)+' i32.sub'
        if kind is ast.UnaryOp and type(node.op) is ast.Not:
            return self.value(node.operand)+' i32.eqz'
        if kind is ast.IfExp:
            return f'{self.value(node.test)} if (result i32) {self.value(node.body)} else {self.value(node.orelse)} end'
        if kind is ast.BoolOp and len(node.values)==2:
            a,b=map(self.value,node.values)
            if type(node.op) is ast.And:
                return f'{a} if (result i32) {b} i32.eqz i32.eqz else i32.const 0 end'
            return f'{a} if (result i32) i32.const 1 else {b} i32.eqz i32.eqz end'
        if kind is ast.Call and type(node.func) is ast.Name and not node.keywords:
            if node.func.id=='pop' and len(node.args)==1:
                return self.value(node.args[0])+' i32.popcnt'
            if node.func.id=='v' and len(node.args)==2:
                return 'local.get $n '+' '.join(map(self.value,node.args))+' call $value'
        raise Refused('EXPRESSION')

    def block(self, statements, loops=()):
        code=[]
        for stmt in statements:
            if type(stmt) is ast.Return and stmt.value is not None:
                code.append(self.value(stmt.value)+' return')
            elif type(stmt) is ast.Assign and len(stmt.targets)==1 and type(stmt.targets[0]) is ast.Name:
                code.append(self.value(stmt.value)+' local.set '+self.locals[stmt.targets[0].id])
            elif type(stmt) is ast.If:
                code.append(f'{self.value(stmt.test)} if {self.block(stmt.body,loops)} else {self.block(stmt.orelse,loops)} end')
            elif type(stmt) is ast.Break and loops:
                code.append('br '+loops[-1][0])
            elif type(stmt) is ast.Continue and loops and self.revision==2:
                code.append('br '+loops[-1][1])
            elif type(stmt) is ast.For and self.valid_loop(stmt,loops):
                self.counter+=1
                loop,end, advance=f'$loop{self.counter}',f'$end{self.counter}',f'$advance{self.counter}'
                i=self.locals[stmt.target.id]
                body=self.block(stmt.body,(*loops,(end,advance)))
                code.append(f'i32.const 0 local.set {i} block {end} loop {loop} '
                            f'local.get {i} local.get $n i32.ge_s br_if {end} block {advance} {body} end '
                            f'local.get {i} i32.const 1 i32.add local.set {i} br {loop} end end')
            else:
                label=type(stmt).__name__
                raise Refused(f'STATEMENT:{label}:{stmt.lineno}' if self.revision==2 else 'STATEMENT')
        return ' '.join(code)

    @staticmethod
    def valid_loop(stmt,loops):
        call=stmt.iter
        return (len(loops)<2 and not stmt.orelse and type(stmt.target) is ast.Name and type(call) is ast.Call and
                type(call.func) is ast.Name and call.func.id=='range' and not call.keywords and len(call.args)==1 and
                type(call.args[0]) is ast.Name and call.args[0].id=='n' and
                not any(isinstance(child,ast.Name) and isinstance(child.ctx,ast.Store) and child.id==stmt.target.id
                        for child_stmt in stmt.body for child in ast.walk(child_stmt)))

    def wat(self):
        locals_=' '.join(f'(local {value} i32)' for value in self.locals.values())
        return f'''(module (memory (export "memory") 1 1)
          (func $value (param $n i32) (param $i i32) (param $j i32) (result i32)
            local.get $i local.get $n i32.ge_u if unreachable end
            local.get $j i32.const {WIDTH} i32.ge_u if unreachable end
            local.get $i i32.const {WIDTH} i32.mul local.get $j i32.add i32.const 4 i32.mul i32.load)
          (func (export "choose") (param $n i32) (param $r i32) (result i32) {locals_}
            {self.body} unreachable))'''


class Program:
    def __init__(self,source,revision=2):
        try:
            import wasmtime as wasm
            if version('wasmtime')!=ENGINE:
                raise Refused('WASMTIME_VERSION')
        except ImportError as error:
            raise Refused('WASMTIME_REQUIRED') from error
        cfg=wasm.Config()
        cfg.consume_fuel=True
        cfg.wasm_threads=False
        cfg.wasm_memory64=False
        cfg.wasm_multi_memory=False
        cfg.parallel_compilation=False
        self.engine=wasm.Engine(cfg)
        self.wasm=wasm
        self.wat=Compiler(source,revision).wat()
        try:
            self.module=wasm.Module(self.engine,self.wat)
        except wasm.WasmtimeError as error:
            raise Refused('COMPILE') from error
        if self.module.imports:
            raise Refused('IMPORT')

    def __call__(self,rows,remaining):
        if not 1<=len(rows)<=LIMIT_ROWS or not 1<=remaining<=LIMIT_ROWS or any(
                len(row)!=WIDTH or any(type(x) is not int or not -(2**31)<=x<2**31 for x in row) for row in rows):
            raise Refused('TABLE')
        wasm=self.wasm
        with wasm.Store(self.engine) as store:
            store.set_limits(memory_size=65536,table_elements=0,instances=1,tables=0,memories=1)
            store.set_fuel(50_000)
            try:
                exports=wasm.Instance(store,self.module,[]).exports(store)
                values=[x for row in rows for x in row]
                exports['memory'].write(store,pack(f'<{len(values)}i',*values),0)
                return exports['choose'](store,len(rows),remaining)
            except (wasm.Trap,wasm.WasmtimeError) as error:
                raise Refused('TRAP_OR_FUEL') from error
