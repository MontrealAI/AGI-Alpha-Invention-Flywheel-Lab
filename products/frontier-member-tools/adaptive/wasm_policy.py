"""Run one typed, untrusted policy with no host capabilities and bounded fuel."""

import ast
from importlib.metadata import version

VERSION = '51.0.0'
INPUTS = ('a','b','c','d','e')
OPS = {'+':('i32.add',2),'-':('i32.sub',2),'*':('i32.mul',2),'/':('i32.div_s',2),
       '<':('i32.lt_s',2),'<=':('i32.le_s',2),'>':('i32.gt_s',2),'>=':('i32.ge_s',2),
       '==':('i32.eq',2),'and':('i32.and',2),'or':('i32.or',2),'choose':('select',3)}


class Refused(ValueError):
    pass


def lower(program):
    if type(program) is not list or not 1<=len(program)<=24:
        raise Refused('PROGRAM_SIZE')
    instructions = []
    depth = 0
    for token in program:
        if type(token) is int and -4096<=token<=4096:
            instructions.append(f'i32.const {token}')
            depth += 1
        elif type(token) is str and token in INPUTS:
            instructions.append(f'local.get {INPUTS.index(token)}')
            depth += 1
        elif type(token) is str and token in OPS:
            instruction,arities=OPS[token]
            if depth<arities:
                raise Refused('PROGRAM_STACK')
            instructions.append(instruction)
            depth -= arities-1
        else:
            raise Refused('PROGRAM_OPCODE')
    if depth!=1:
        raise Refused('PROGRAM_RESULT')
    return '(module (func (export "choose") (param i32 i32 i32 i32 i32) (result i32) '+' '.join(instructions)+'))'


def expression_wat(expression):
    """Compile a portable integer expression. Never evaluate it as Python."""
    if not isinstance(expression,str) or not 0<len(expression.encode())<=256:
        raise Refused('EXPRESSION_SIZE')
    try:
        root=ast.parse(expression.strip(),mode='eval')
    except SyntaxError as error:
        raise Refused('EXPRESSION_SYNTAX') from error
    if sum(1 for _ in ast.walk(root))>48:
        raise Refused('EXPRESSION_COMPLEXITY')

    binary={ast.Add:'i32.add',ast.Sub:'i32.sub',ast.Mult:'i32.mul'}
    compare={ast.Lt:'i32.lt_s',ast.LtE:'i32.le_s',ast.Gt:'i32.gt_s',ast.GtE:'i32.ge_s',ast.Eq:'i32.eq'}

    def emit(node):
        if isinstance(node,ast.Constant) and type(node.value)is int and 0<=node.value<=4096:
            return f'i32.const {node.value}'
        if isinstance(node,ast.Name) and node.id in INPUTS:
            return f'local.get {INPUTS.index(node.id)}'
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.USub):
            return f'i32.const 0 {emit(node.operand)} i32.sub'
        if isinstance(node,ast.BinOp) and type(node.op) in binary:
            return f'{emit(node.left)} {emit(node.right)} {binary[type(node.op)]}'
        if isinstance(node,ast.Compare) and len(node.ops)==1 and type(node.ops[0]) in compare:
            return f'{emit(node.left)} {emit(node.comparators[0])} {compare[type(node.ops[0])]}'
        if isinstance(node,ast.IfExp):
            return f'{emit(node.test)} if (result i32) {emit(node.body)} else {emit(node.orelse)} end'
        raise Refused('EXPRESSION_OPERATION')

    code=emit(root.body)
    return '(module (func (export "choose") (param i32 i32 i32 i32 i32) (result i32) '+code+'))'


class Policy:
    def __init__(self, wat):
        if not isinstance(wat,str) or not 1 <= len(wat.encode()) <= 4096:
            raise Refused('WASM_SOURCE_SIZE')
        try:
            import wasmtime as wasm
        except ImportError as error:
            raise Refused('WASMTIME_REQUIRED') from error
        if version('wasmtime') != VERSION:
            raise Refused('WASMTIME_VERSION')
        settings = wasm.Config()
        settings.consume_fuel = True
        settings.wasm_threads = False
        settings.wasm_memory64 = False
        settings.wasm_multi_memory = False
        settings.parallel_compilation = False
        settings.max_wasm_stack = 65536
        self.engine = wasm.Engine(settings)
        self.wasm = wasm
        try:
            self.module = wasm.Module(self.engine, wat)
        except wasm.WasmtimeError as error:
            raise Refused('WASM_COMPILE') from error
        exports = self.module.exports
        if self.module.imports:
            raise Refused('WASM_IMPORTS_DENIED')
        if len(exports) != 1 or exports[0].name != 'choose':
            raise Refused('WASM_EXPORT')
        sig = exports[0].type
        if not isinstance(sig,wasm.FuncType) or sig.params != [wasm.ValType.i32()]*5 or sig.results != [wasm.ValType.i32()]:
            raise Refused('WASM_SIGNATURE')

    def __call__(self, *inputs):
        if len(inputs) != 5 or any(type(x) is not int or not -2**31 <= x < 2**31 for x in inputs):
            raise Refused('WASM_INPUT')
        wasm = self.wasm
        with wasm.Store(self.engine) as store:
            store.set_limits(memory_size=65536,table_elements=64,instances=1,tables=1,memories=1)
            store.set_fuel(3000)
            try:
                instance = wasm.Instance(store,self.module,[])
                return instance.exports(store)['choose'](store,*inputs)
            except (wasm.WasmtimeError,wasm.Trap) as error:
                raise Refused('WASM_RESOURCE_OR_TRAP') from error
