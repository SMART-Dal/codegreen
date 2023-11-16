from _ast import FunctionDef
import ast
from pprint import pprint
import copy
import json
import argparse
from typing import Any
import os
from codegreen.fecom.patching.patching_config import PROJECT_PATH, TOOL_INSTALLATION_PATH

# parser = argparse.ArgumentParser()
# parser.add_argument("input_files", type=argparse.FileType("r"))
# args = parser.parse_args()

requiredLibraries = ["tensorflow"]
requiredAlias = []
requiredObjects = []
requiredObjectsSignature = {}
requiredClassDefs = {}
requiredObjClassMapping = {}
importScriptList = ""
sourceCode = ""


def method_level_patcher(script_path_to_be_patched,metadata):
    # Step1: Create an AST from the client python code
    global sourceCode
    # global args
    with open(script_path_to_be_patched, 'r') as file:
        sourceCode = file.read()
    tree = ast.parse(sourceCode)
    # print('+'*100)
    # print(ast.dump(tree, indent=4))
    # print('_'*100)

    # Step2: Extract list of libraries and aliases for energy calculation
    analyzer = Analyzer()
    analyzer.visit(tree)
    global requiredAlias
    global importScriptList
    global importMap
    importMap = analyzer.importMap
    requiredAlias = analyzer.stats["required"]
    importScriptList = list(set(analyzer.stats["importScript"]))

    if not requiredAlias:
        return

    # Get list of libraries and aliases with __future__ imports as they need to be moved to the beginning
    future_imports = [
        imp for imp in importScriptList if imp.startswith("from __future__")
    ]

    # Get list of libraries and aliases without __future__ imports
    importScriptList = [
        imp for imp in importScriptList if not imp.startswith("from __future__")
    ]

    # Add __future__ imports to the beginning of the list
    importScriptList = future_imports + importScriptList

    importScriptList = ";".join(importScriptList)

    # Step3: Get list of Classdefs having bases from the required libraries
    global requiredClassDefs
    global requiredClassBase
    classDefAnalyzer = ClassDefAnalyzer()
    classDefAnalyzer.visit(tree)
    requiredClassDefs = classDefAnalyzer.classDef
    requiredClassBase = classDefAnalyzer.classBases

    # Step4: Get list of objects created from the required libraries
    global requiredObjects
    global requiredObjectsSignature
    global requiredObjClassMapping
    objAnalyzer = ObjectAnalyzer()
    objAnalyzer.visit(tree)
    requiredObjects = objAnalyzer.stats["objects"]

    # create nodes to add before and after the method call
    before_execution_call = (
        "start_times_INSERTED_INTO_SCRIPT = before_execution_INSERTED_INTO_SCRIPT(experiment_file_path = None, function_to_run = None)"
    )
    global before_execution_call_node
    before_execution_call_node = ast.parse(before_execution_call)
    # print(ast.dump(before_execution_call_node))

    # Step5: Tranform the client script by adding custom method calls
    transf = TransformCall(metadata)
    transf.visit(tree)

    with open(TOOL_INSTALLATION_PATH / 'patching/method_level_patch_imports.py', "r") as source:
        cm = source.read()
        cm_node = ast.parse(cm)

        first_import = 0
        while first_import < len(tree.body) and not isinstance(
            tree.body[first_import], (ast.Import, ast.ImportFrom)
        ):
            first_import += 1

        first_non_import = first_import
        while first_non_import < len(tree.body) and isinstance(
            tree.body[first_non_import], (ast.Import, ast.ImportFrom)
        ):
            first_non_import += 1
        # Insert the new import statement before the first non-import statement
        tree.body.insert(first_non_import, cm_node)

    # print('+'*100)
    # import traceback
    # try:
    #     print(ast.dump(tree, indent=4))
    # except:
    #     traceback.print_exc()
    # print('_'*100)

    # Step6: Unparse and convert AST to final code
    # print(ast.unparse(tree))
    patched_code = ast.unparse(tree)

    # Write the patched code back to the file
    with open(script_path_to_be_patched, 'w') as file:
        file.write(patched_code)

    return requiredAlias

class FuncCallVisitor(ast.NodeVisitor):
    def __init__(self):
        self.name_list = []

    def visit_Name(self, node):
        self.name_list.append(node.id)
        return self.name_list

    def visit_Attribute(self, node):
        self.visit(node.value)
        self.name_list.append(node.attr)
        return self.name_list

    def visit_Call(self, node):
        callvisitor = FuncCallVisitor()
        callvisitor.visit(node.func)
        call_list = callvisitor.get_name_list()
        self.name_list.extend(call_list)
        return call_list

    def get_name_list(self):
        return self.name_list


class TransformCall(ast.NodeTransformer):
    def __init__(self, metadata):
        global requiredAlias
        global sourceCode
        global requiredObjects
        global requiredObjClassMapping
        global requiredObjectsSignature
        global requiredClassDefs
        global requiredClassBase
        global before_execution_call_node
        global importMap
        self.objectname = None
        self.metadata = metadata

    def get_target_id(self, target):
        if isinstance(target, ast.Name):
            return target.id
        elif isinstance(target, ast.Tuple):
            return ", ".join(self.get_target_id(elt) for elt in target.elts)
        elif isinstance(target, ast.Attribute):
            return target.attr
        elif isinstance(target, ast.Subscript):
            target_id = self.get_target_id(target.value)
            if isinstance(target.slice, ast.Index):
                index_id = self.get_target_id(target.slice.value)
                return f"{target_id}[{index_id}]"
            elif isinstance(target.slice, ast.Slice):
                start_id = (
                    self.get_target_id(target.slice.lower) if target.slice.lower else ""
                )
                stop_id = (
                    self.get_target_id(target.slice.upper) if target.slice.upper else ""
                )
                step_id = (
                    self.get_target_id(target.slice.step) if target.slice.step else ""
                )
                if start_id or stop_id or step_id:
                    return f"{target_id}[{start_id}:{stop_id}:{step_id}]"
                else:
                    return f"{target_id}[:]"
            elif isinstance(target.slice, ast.ExtSlice):
                dim_ids = [self.get_target_id(d) for d in target.slice.dims]
                return f"{target_id}[{', '.join(dim_ids)}]"
            elif isinstance(target.slice, ast.Name):
                return f"{target_id}[{target.slice.id}]"
            elif isinstance(target.slice, ast.Constant):
                return f"{target_id}[{target.slice.value}]"
            elif isinstance(target.slice, ast.Tuple):
                return f"{target_id}[{', '.join(self.get_target_id(elt) for elt in target.slice.elts)}]"
            else:
                return ""
                # raise ValueError("Unsupported target type")
        elif isinstance(target, ast.Starred):
            return f"*{self.get_target_id(target.value)}"
        else:
            return ""  # covered multiple types of object, add in future if some complex type are missing
            # raise ValueError("Unsupported target type")

    def get_func_name(self, value):
        if isinstance(value, ast.Call):
            if isinstance(value.func, ast.Name):
                return value.func.id
            elif isinstance(value.func, ast.Attribute):
                return value.func.attr
            elif isinstance(value.func, ast.Call):
                return self.get_func_name(value.func)
            else:
                return None
                # raise ValueError("Unsupported function type")
        elif isinstance(value, ast.BinOp):
            return self.get_func_name(value.left)
        else:
            # print("Unsupported value type")
            return None

    def visit_Assign(self, node):
        target = node.targets[0]
        self.objectname = self.get_target_id(target)
        classname = self.get_func_name(node.value)
        modified_node = None  # Initialize modified_node as None
        if classname and classname in list(requiredClassDefs.keys()):
            requiredObjClassMapping[self.objectname] = classname
            requiredObjectsSignature[self.objectname] = ast.get_source_segment(
                sourceCode, node.value
            )

        if isinstance(node.value, ast.Call):
            modified_node = self.custom_Call(node.value)
            createObjectSignature = ast.get_source_segment(sourceCode, node.value.func)
            requiredObjectsSignature[self.objectname] = (
                createObjectSignature
                if not requiredObjectsSignature.get(createObjectSignature.split(".")[0])
                else createObjectSignature.replace(
                    createObjectSignature.split(".")[0],
                    requiredObjectsSignature.get(createObjectSignature.split(".")[0]),
                    1,
                )
            )

        if modified_node and modified_node != node.value:
            # print("modified_node[0] :", ast.dump(modified_node[0]))
            before_execution_call_node_copy = copy.deepcopy(before_execution_call_node)
            before_execution_call_node_copy.body[0].value.keywords[1] = (ast.keyword(arg='function_to_run', value=modified_node[0].keywords[2].value))
            before_execution_call_node_copy.body[0].value.keywords[0] = (ast.keyword(arg='experiment_file_path', value=modified_node[0].keywords[1].value))
            return [before_execution_call_node_copy, node, ast.Expr(value=modified_node[0])]

        return node

    def visit_Expr(self, node):
        if isinstance(node.value, ast.Call):
            modified_node = None  # Initialize modified_node as None
            modified_node = self.custom_Call(node.value)
            if modified_node and modified_node != node.value:
                before_execution_call_node_copy = copy.deepcopy(before_execution_call_node)
                # print("modified_node[0] :", modified_node[0])
                before_execution_call_node_copy.body[0].value.keywords[1] = (ast.keyword(arg='function_to_run', value=modified_node[0].keywords[2].value))
                before_execution_call_node_copy.body[0].value.keywords[0] = (ast.keyword(arg='experiment_file_path', value=modified_node[0].keywords[1].value))
                return [
                    before_execution_call_node_copy,
                    node,
                    ast.Expr(value=modified_node[0]),
                ]
        return node

    def custom_Call(self, node):
        callvisitor = FuncCallVisitor()
        callvisitor.visit(node.func)
        callvisitor_list = callvisitor.get_name_list()

        self.metadata["api_call_line"] = node.lineno

        # print("callvisitor_list :",callvisitor_list,"requiredObjectsSignature :",requiredObjectsSignature,"requiredAlias :",requiredAlias,"requiredObjects :",requiredObjects)
        if any(lib in callvisitor.get_name_list() for lib in requiredAlias) and (
            importMap.get(callvisitor_list[0])
        ):
            dummyNode = copy.deepcopy(node)
            dummyNode.args.clear()
            dummyNode.keywords.clear()
            # argList = [ast.get_source_segment(sourceCode, a) for a in node.args]
            argList = [a for a in node.args]
            # keywordsDict = {a.arg:ast.get_source_segment(sourceCode, a.value) for a in node.keywords}
            keywordsDict = {a.arg: a.value for a in node.keywords}
            # if(node.args):
            #     dummyNode.args.append(ast.Name(id='*args', ctx=ast.Load()))
            # if(node.keywords):
            #     dummyNode.keywords.append(ast.Name(id='**kwargs', ctx=ast.Load()))
            new_node = ast.Call(
                func=ast.Name(
                    id="after_execution_INSERTED_INTO_SCRIPT", ctx=ast.Load()
                ),
                args=[],
                keywords=[
                    ast.keyword(
                        arg="start_times",
                        value=ast.Name(id="start_times_INSERTED_INTO_SCRIPT"),
                    ),
                    ast.keyword(
                        arg="experiment_file_path",
                        value=ast.Name(id="EXPERIMENT_FILE_PATH"),
                    ),
                    ast.keyword(
                        arg="function_to_run",
                        value=ast.Constant(
                            ast.unparse(dummyNode).replace(
                                callvisitor_list[0],
                                importMap.get(callvisitor_list[0]),
                                1,
                            )
                        ),
                    ),
                    ast.keyword(
                        arg="project_metadata",
                        value=ast.Dict(keys=[ast.Constant(value=key) for key, _ in self.metadata.items()],
                              values=[ast.Constant(value=value) for _, value in self.metadata.items()]),
                    ),
                    ast.keyword(arg="method_object", value=ast.Constant(None)),
                    ast.keyword(
                        arg="function_args",
                        value=ast.List(
                            elts=[argItem for argItem in argList], ctx=ast.Load()
                        )
                        if argList
                        else ast.Constant(None),
                    ),
                    ast.keyword(
                        arg="function_kwargs",
                        value=ast.Dict(
                            keys=[ast.Constant(KWItem) for KWItem in keywordsDict],
                            values=[keywordsDict[KWItem] for KWItem in keywordsDict],
                        )
                        if keywordsDict
                        else ast.Constant(None),
                    ),
                ],
                starargs=None,
                kwargs=None,
            )

            ast.copy_location(new_node, node)
            ast.fix_missing_locations(new_node)
            # return [ast.Expr(value=new_node), ast.Expr(value=node)]
            return [new_node, node]
        elif (
            callvisitor_list
            and (callvisitor_list[0] in requiredObjects)
            and (
                requiredClassBase.get(requiredObjectsSignature.get(callvisitor_list[0]))
            )
            and (
                requiredObjClassMapping.get(callvisitor_list[0])
                in list(requiredClassDefs.keys())
            )
        ):
            dummyNode = copy.deepcopy(node)
            dummyNode.args.clear()
            dummyNode.keywords.clear()
            # argList = [ast.get_source_segment(sourceCode, a) for a in node.args]
            argList = [a for a in node.args]
            # keywordsDict = {a.arg:ast.get_source_segment(sourceCode, a.value) for a in node.keywords}
            keywordsDict = {a.arg: a.value for a in node.keywords}
            # if(node.args):
            #     dummyNode.args.append(ast.Name(id='*args', ctx=ast.Load()))
            # if(node.keywords):
            #     dummyNode.keywords.append(ast.Name(id='**kwargs', ctx=ast.Load()))
            new_node = ast.Call(
                func=ast.Name(
                    id="after_execution_INSERTED_INTO_SCRIPT", ctx=ast.Load()
                ),
                args=[],
                keywords=[
                    ast.keyword(
                        arg="start_times",
                        value=ast.Name(id="start_times_INSERTED_INTO_SCRIPT"),
                    ),
                    ast.keyword(
                        arg="experiment_file_path",
                        value=ast.Name(id="EXPERIMENT_FILE_PATH"),
                    ),
                    ast.keyword(
                        arg="function_to_run",
                        value=ast.Constant(
                            ast.unparse(dummyNode).replace(
                                callvisitor_list[0],
                                (
                                    requiredClassBase.get(
                                        requiredObjectsSignature.get(
                                            callvisitor_list[0]
                                        )
                                    ).replace(
                                        requiredClassBase.get(
                                            requiredObjectsSignature.get(
                                                callvisitor_list[0]
                                            )
                                        ).split(".")[0],
                                        importMap.get(
                                            requiredClassBase.get(
                                                requiredObjectsSignature.get(
                                                    callvisitor_list[0]
                                                )
                                            ).split(".")[0]
                                        ),
                                        1,
                                    )
                                ),
                                1,
                            )
                        ),
                    ),
                    ast.keyword(
                        arg="project_metadata",
                        value=ast.Dict(keys=[ast.Constant(value=key) for key, _ in self.metadata.items()],
                              values=[ast.Constant(value=value) for _, value in self.metadata.items()]),
                    ),
                    ast.keyword(
                        arg="method_object", value=ast.Name(callvisitor_list[0])
                    ),
                    ast.keyword(
                        arg="function_args",
                        value=ast.List(
                            elts=[argItem for argItem in argList], ctx=ast.Load()
                        )
                        if argList
                        else ast.Constant(None),
                    ),
                    ast.keyword(
                        arg="function_kwargs",
                        value=ast.Dict(
                            keys=[ast.Constant(KWItem) for KWItem in keywordsDict],
                            values=[keywordsDict[KWItem] for KWItem in keywordsDict],
                        )
                        if keywordsDict
                        else ast.Constant(None),
                    ),
                ],
                starargs=None,
                kwargs=None,
            )
            ast.copy_location(new_node, node)
            ast.fix_missing_locations(new_node)
            # return [ast.Expr(value=new_node), ast.Expr(value=node)]
            return [new_node, node]
        elif (
            callvisitor_list
            and (callvisitor_list[0] in requiredObjects)
            and (
                requiredObjectsSignature.get(callvisitor_list[0])
                and (
                    importMap.get(
                        requiredObjectsSignature.get(callvisitor_list[0]).split(".")[0]
                    )
                )
                and any(
                    lib in requiredObjectsSignature.get(callvisitor_list[0])
                    for lib in requiredAlias
                )
            )
        ):
            dummyNode = copy.deepcopy(node)
            dummyNode.args.clear()
            dummyNode.keywords.clear()
            # argList = [ast.get_source_segment(sourceCode, a) for a in node.args]
            argList = [a for a in node.args]
            # keywordsDict = {a.arg:ast.get_source_segment(sourceCode, a.value) for a in node.keywords}
            keywordsDict = {a.arg: a.value for a in node.keywords}
            # if(node.args):
            #     dummyNode.args.append(ast.Name(id='*args', ctx=ast.Load()))
            # if(node.keywords):
            #     dummyNode.keywords.append(ast.Name(id='**kwargs', ctx=ast.Load()))
            new_node = ast.Call(
                func=ast.Name(
                    id="after_execution_INSERTED_INTO_SCRIPT", ctx=ast.Load()
                ),
                args=[],
                keywords=[
                    ast.keyword(
                        arg="start_times",
                        value=ast.Name(id="start_times_INSERTED_INTO_SCRIPT"),
                    ),
                    ast.keyword(
                        arg="experiment_file_path",
                        value=ast.Name(id="EXPERIMENT_FILE_PATH"),
                    ),
                    ast.keyword(
                        arg="function_to_run",
                        value=ast.Constant(
                            ast.unparse(dummyNode).replace(
                                callvisitor_list[0],
                                requiredObjectsSignature.get(
                                    callvisitor_list[0]
                                ).replace(
                                    requiredObjectsSignature.get(
                                        callvisitor_list[0]
                                    ).split(".")[0],
                                    importMap.get(
                                        requiredObjectsSignature.get(
                                            callvisitor_list[0]
                                        ).split(".")[0]
                                    ),
                                    1,
                                ),
                                1,
                            )
                        ),
                    ),
                    ast.keyword(
                        arg="project_metadata",
                        value=ast.Dict(keys=[ast.Constant(value=key) for key, _ in self.metadata.items()],
                              values=[ast.Constant(value=value) for _, value in self.metadata.items()]),
                    ),
                    ast.keyword(
                        arg="method_object", value=ast.Name(callvisitor_list[0])
                    ),
                    ast.keyword(
                        arg="function_args",
                        value=ast.List(
                            elts=[argItem for argItem in argList], ctx=ast.Load()
                        )
                        if argList
                        else ast.Constant(None),
                    ),
                    ast.keyword(
                        arg="function_kwargs",
                        value=ast.Dict(
                            keys=[ast.Constant(KWItem) for KWItem in keywordsDict],
                            values=[keywordsDict[KWItem] for KWItem in keywordsDict],
                        )
                        if keywordsDict
                        else ast.Constant(None),
                    ),
                ],
                starargs=None,
                kwargs=None,
            )
            ast.copy_location(new_node, node)
            ast.fix_missing_locations(new_node)
            # return [ast.Expr(value=new_node), ast.Expr(value=node)]
            return [new_node, node]

        return node


class Analyzer(ast.NodeVisitor):
    def __init__(self):
        self.stats = {"import": [], "from": [], "required": [], "importScript": []}
        self.importMap = {}
        global sourceCode

    def visit_Import(self, node):
        for alias in node.names:
            self.stats["importScript"].append(ast.get_source_segment(sourceCode, node))
            self.stats["import"].append(alias.name)
            lib_path = alias.name.split(".")
            if any(lib in lib_path for lib in requiredLibraries):
                if alias.asname:
                    self.stats["required"].append(alias.asname)
                    self.importMap[alias.asname] = alias.name
                else:
                    self.stats["required"].append(lib_path[-1])
                    self.importMap[lib_path[-1]] = alias.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if(node.module):
            lib_path = node.module.split(".")
            for alias in node.names:
                self.stats["importScript"].append(ast.get_source_segment(sourceCode, node))
                self.stats["from"].append(alias.name)
                if any(lib in lib_path for lib in requiredLibraries):
                    if alias.asname:
                        self.stats["required"].append(alias.asname)
                        self.importMap[alias.asname] = node.module + "." + alias.name
                    elif alias.name == "*":
                        pass
                    else:
                        self.stats["required"].append(alias.name)
                        self.importMap[alias.name] = node.module + "." + alias.name
        self.generic_visit(node)

    def report(self):
        pprint(self.stats)


class ClassDefAnalyzer(ast.NodeVisitor):
    def __init__(self):
        self.classDef = {}
        self.classBases = {}
        global sourceCode

    def visit_ClassDef(self, node):
        if (node.bases) and any(
            ast.get_source_segment(sourceCode, lib).split(".")[0] in requiredAlias
            for lib in node.bases
        ):
            self.classDef[node.name] = ast.get_source_segment(sourceCode, node)
            # This logic only covers classes that inherit from one base class
            self.classBases[node.name] = ast.get_source_segment(
                sourceCode, node.bases[0]
            )

        if (node.bases) and any(
            ast.get_source_segment(sourceCode, lib).split(".")[0]
            in list(self.classDef.keys())
            for lib in node.bases
        ):
            self.classDef[node.name] = ast.get_source_segment(sourceCode, node)
            # This logic only covers classes that inherit from one base class
            self.classBases[node.name] = self.classBases[
                ast.get_source_segment(sourceCode, node.bases[0])
            ]


class ObjectAnalyzer(ast.NodeVisitor):
    def __init__(self):
        self.stats = {"objects": []}
        self.methodReturn = {}
        global sourceCode
        global requiredClassDefs

    def visit_Assign(self, node):
        if isinstance(node.value, ast.Call):
            callvisitor2 = FuncCallVisitor()
            callvisitor2.visit(node.value.func)
            name_list = callvisitor2.get_name_list()
            if (
                name_list
                and (any(lib in name_list for lib in requiredAlias))
                and (isinstance(node.targets[0], ast.Name))
            ):
                self.stats["objects"].append(node.targets[0].id)

            if (
                name_list
                and (any(lib in name_list[0] for lib in list(requiredClassDefs.keys())))
                and (isinstance(node.targets[0], ast.Name))
            ):
                self.stats["objects"].append(node.targets[0].id)

            if (
                name_list
                and (any(obj in name_list[0] for obj in self.stats["objects"]))
                and (isinstance(node.targets[0], ast.Name))
            ):
                self.stats["objects"].append(node.targets[0].id)

        self.generic_visit(node)


# if __name__ == "__main__":
#     method_level_patcher(script_to_be_patched)
