import onnx
import torch

from onnx_pytorch.op_code_generators import OpCodeGenerator


class GatherOpCodeGenerator(OpCodeGenerator):

  def __init__(self,
               onnx_ver=onnx.defs.onnx_opset_version(),
               torch_ver=torch.__version__):
    super(GatherOpCodeGenerator, self).__init__(onnx_ver, torch_ver)
    self.embedding_conf = None

  def gen(self, node, value_infos, initializers):
    attr_value_dict = self.get_attr_value_dict(node)
    inputs_str, outputs_str = self.gen_input_output_string(
        node, initializers, self.rename_helper, self.tensor_inplace)
    init_str, forward_str = [], []
    if self.embedding_conf is not None and node.name in self.embedding_conf:
      node_name = self.rename_helper.get_node_name(node.name, node.op_type)
      params_str = self.gen_params_str(
          num_embeddings=self.embedding_conf[node.name].num_embeddings,
          embedding_dim=self.embedding_conf[node.name].embedding_dim)
      weights = onnx.numpy_helper.to_array(initializers[node.input[0]])
      if weights.shape[0] == self.embedding_conf[node.name].num_embeddings:
        init_str.append(
            f"self.{node_name} = nn.Embedding.from_pretrained({inputs_str[0]}, freeze=False)"
        )
      else:
        init_str.append(f"self.{node_name} = nn.Embedding(**{{{params_str}}})")
      forward_str.append(
          f"{outputs_str[0]} = self.{node_name}({inputs_str[1]})")
    else:
      axis = attr_value_dict.get("axis", 0)
      forward_str.append(
          f"{outputs_str[0]} = {inputs_str[0]}.__getitem__([slice(None) for _ in range({axis})] + [{inputs_str[1]}.to(torch.int64)])"
      )
    return {"init": init_str, "forward": forward_str}
