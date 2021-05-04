import collections
import os
import shutil

import onnx

TENSOR_PREFIX = "_t_"
HEADER = f'''# Autogenerated by onnx-model-maker. Don't modify it manually.

import onnx
import onnx.helper
import onnx.numpy_helper
from onnx_model_maker import omm
from onnx_model_maker import onnx_mm_export
from onnx_model_maker.ops.op_helper import _add_input
'''

OP_HELPER_PY = f'''from uuid import uuid4

import numpy
import onnx

from onnx_model_maker import omm


def _add_input(target, inputs):
  if target is None:
    return
  if type(target) == numpy.ndarray:
    t = onnx.numpy_helper.from_array(target, f"{TENSOR_PREFIX}{{uuid4().hex[:4]}}")
    omm.model.graph.initializer.append(t)
    inputs.append(t.name)
  elif type(target) == str:
    inputs.append(target)
  elif type(target) == list and all([type(i) == str for i in target]):
    inputs.extend(target)
  elif type(target) == onnx.NodeProto:
    inputs.append(target.output[0])
'''

INIT_PY = f'''import glob
import importlib
import os
import sys

import onnx
import numpy

from onnx_model_maker import mod_name
from onnx_model_maker import omm
from onnx_model_maker import OPSET_VER


modules = glob.glob(os.path.join(os.path.dirname(__file__), "op_ver_*.py"))
for m in modules:
  spec = importlib.util.spec_from_file_location(os.path.basename(m)[:-3], m)
  spec.loader.exec_module(importlib.util.module_from_spec(spec))


def Input(*args):
  inputs = []
  for i, a in enumerate(args):
    t = onnx.numpy_helper.from_array(a)
    vi = onnx.helper.make_tensor_value_info(f"{TENSOR_PREFIX}Input_{{i}}",
                                            t.data_type, t.dims)
    omm.model.graph.input.append(vi)
    inputs.append(vi.name)
  return inputs


def Output(*args):
  for i, a in enumerate(args):
    if type(a) == numpy.ndarray:
      t = onnx.numpy_helper.from_array(a)
      vi = onnx.helper.make_tensor_value_info(f"{TENSOR_PREFIX}Output_{{i}}", t.data_type,
                                              t.dims)
      omm.model.graph.output.append(vi)
    elif type(a) == str:
      vi = onnx.helper.make_empty_tensor_value_info(a)
      omm.model.graph.output.append(vi)
    elif type(a) == onnx.NodeProto:
      for o in a.output:
        vi = onnx.helper.make_empty_tensor_value_info(o)
        omm.model.graph.output.append(vi)
    else:
      raise Exception


'''


def _gen_op_maker(schema):
  onnx_op = schema.name
  inputs_args = [
      i.name if idx < schema.min_input else f"{i.name}=None"
      for idx, i in enumerate(schema.inputs)
  ]
  inputs_forloop = [i.name for i in schema.inputs]
  if len(schema.inputs) == 1:
    inputs_forloop.append("")
  if len(schema.inputs) != 0:
    inputs_args.append("")

  outputs_str = f'[f"{TENSOR_PREFIX}{onnx_op}_{{idx}}"]'
  if schema.name == "Split":
    if schema.since_version == 13:
      outputs_str = f'[f"{TENSOR_PREFIX}{onnx_op}_{{idx}}_{{i}}" for i in range(len(split))]'
    else:
      outputs_str = f'[f"{TENSOR_PREFIX}{onnx_op}_{{idx}}_{{i}}" for i in range(len(kwargs["split"]))]'

  return f'''@onnx_mm_export("v{schema.since_version}.{onnx_op}")
def {onnx_op}({', '.join(inputs_args)}**kwargs):
  _inputs = []
  for i in ({', '.join(inputs_forloop)}):
    _add_input(i, _inputs)

  idx = omm.op_counter[\"{onnx_op}\"]
  omm.op_counter[\"{onnx_op}\"] += 1
  node = onnx.helper.make_node(\"{onnx_op}\",
                               _inputs, {outputs_str},
                               name=f"{onnx_op}_{{idx}}",
                               **kwargs)
  onnx.checker.check_node(node, omm.ctx)
  omm.model.graph.node.append(node)
  return node
'''


def _gen_abs_op_maker(schema):
  onnx_op = schema.name
  return f'''def {onnx_op}(*args, **kwargs):
  schema = onnx.defs.get_schema("{onnx_op}",
                                max_inclusive_version=OPSET_VER,
                                domain="")
  return getattr(sys.modules[f"{{mod_name}}.ops"], 
                 f"v{{schema.since_version}}.{onnx_op}")(*args, **kwargs)
'''


def gen(output_dir=None, overwrite=False):
  if overwrite:
    shutil.rmtree(output_dir)
    os.makedirs(output_dir)
  if not os.path.exists(output_dir):
    os.makedirs(output_dir)
  abs_op_contents = {}
  file_contents = collections.defaultdict(list)
  all_schemas = onnx.defs.get_all_schemas_with_history()
  for schema in all_schemas:
    since_version = schema.since_version
    if str(since_version) not in file_contents:
      file_contents[str(since_version)].append(HEADER)
    if schema.name not in abs_op_contents:
      abs_op_contents[schema.name] = _gen_abs_op_maker(schema)
    file_contents[str(since_version)].append(_gen_op_maker(schema))
  for v, c in file_contents.items():
    with open(os.path.join(output_dir, f"op_ver_{v}.py"), "w") as f:
      f.write('''

'''.join(c))
  with open(os.path.join(output_dir, "__init__.py"), "w") as f:
    f.write(INIT_PY)
    f.write('''

'''.join([abs_op_contents[key] for key in sorted(abs_op_contents.keys())]))
    all_str = ', '.join([f'"{key}"' for key in sorted(abs_op_contents.keys())])
    f.write(f'''

__all__ = [\"Input\", \"Output\", {all_str}]''')
  with open(os.path.join(output_dir, "op_helper.py"), "w") as f:
    f.write(OP_HELPER_PY)


gen("./ops")
