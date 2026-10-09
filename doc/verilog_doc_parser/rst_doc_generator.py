# This file is part of the OpenEye project.
# © Fachhochschule Dortmund – University of Applied Sciences and Arts (until 2025), Universität Duisburg-Essen (since 2025).
# SPDX-License-Identifier: SHL-2.1
# For more details, see the LICENSE file in the root directory of this project.
import os
import re
import warnings
from subprocess import Popen, PIPE

import logging
logger = logging.getLogger("doc")

from textwrap import indent

from docstring_parser import parse_documentation
from moduledef_parser import parse_module_def


BULLET_RE = re.compile(r'^\s*([-*+•]|\d+[.)])\s')


def escape_rst(text):
    """
    Escape characters that reStructuredText would interpret as markup.

    "|" starts a substitution reference in RST, so ASCII timing diagrams such as
    "clk : __|‾‾|__" in the Verilog comments would produce
    "Undefined substitution referenced" errors.
    """
    return text.replace("|", r"\|")


def separate_bullet_lists(text):
    """
    Insert blank lines where a bullet list starts or ends.

    The docstring parser strips the indentation of every comment line, so a bullet
    list is often directly followed by a normal text line, and nested lists
    ("- Group:" followed by "* item") end up on the same level with a different
    bullet character. RST requires a blank line in both cases and otherwise warns
    "Bullet list ends without a blank line".
    """
    lines = []
    prev_kind = None  # None: previous line was blank (or there is none)
    for line in text.split("\n"):
        if not line.strip():
            lines.append(line)
            prev_kind = None
            continue
        match = BULLET_RE.match(line)
        # "text" for normal lines, the bullet marker (or "enum") for list items
        if match is None:
            kind = "text"
        elif match.group(1)[0].isdigit():
            kind = "enum"
        else:
            kind = match.group(1)
        if prev_kind is not None and prev_kind != kind:
            lines.append("")
        lines.append(line)
        prev_kind = kind
    return "\n".join(lines)


def format_description(text):
    return separate_bullet_lists(escape_rst(text))


def generate_rst(doc, module_def, image_name=None):
    """
    Generate RST documentation for a Verilog module.

    The module signature and the parameter/port lists are taken from the actual
    module definition, so undocumented ports (or a missing "Ports:" section) still
    produce a valid page. Descriptions are taken from the docstring when present;
    documented names that do not exist in the module are skipped.

    Args:
        doc: ModuleDocumentation object from parse_documentation()
        module_def: ModuleDefinition object from parse_module_def()
        image_name: Filename of the module symbol image, or None if there is no image

    Returns:
        String containing the RST documentation
    """
    docstring = ""

    title = f"{doc.module_name}"
    docstring += title + "\n"
    docstring += "=" * len(title) + "\n\n"

    docstring += f".. verilog:module:: module {doc.module_name}"
    if module_def.ports:
        docstring += "(" + ", ".join(module_def.ports) + ")"
    docstring += "\n\n"

    indented_description = indent(format_description(doc.description), "    ")

    docstring += f"{indented_description}\n\n"

    if image_name:
        docstring += f"    .. image:: {image_name} \n\n"

    for param in doc.parameters:
        if param not in module_def.parameters:
            logger.debug(f"Parameter {param} documented but not found in module definition for {doc.module_name}")
    for port in doc.ports:
        if port not in module_def.ports:
            logger.debug(f"Port {port} documented but not found in module definition for {doc.module_name}")

    # Add parameters in declaration order
    for param in module_def.parameters:
        desc = indent(format_description(doc.parameters.get(param, "")), "        ")
        param_type = module_def.parameters[param].ptype
        param_default = module_def.parameters[param].default_value
        docstring += f"    .. verilog:parameter:: parameter {param_type} {param} = {param_default}\n\n"
        docstring += f"{desc}\n\n"

    # Add ports in declaration order
    for port in module_def.ports:
        desc = indent(format_description(doc.ports.get(port, "")), "        ")

        port_direction = module_def.ports[port].direction
        port_sign = module_def.ports[port].sign
        port_type = module_def.ports[port].type
        port_upper = module_def.ports[port].range_upper
        port_lower = module_def.ports[port].range_lower

        docstring += f"    .. verilog:port:: {port_direction} {port_sign} {port_type} {port} "
        if port_upper!= 1 or port_lower != 0:
            docstring += f"[{port_upper}:{port_lower}]\n\n"
        else:
            docstring += "\n\n"
        docstring += f"        {desc}\n\n"

    return docstring


def generate_rst_file(input_filename):
    with open(input_filename, "r") as f_input:
        text = f_input.read()
        doc = parse_documentation(text)
        module_def = parse_module_def(text)
        doc_dir = __file__.split("/")[:-2]
        doc_dir.extend(["source", "verilog"])
        # Only reference the symbol image if symbolator actually created it,
        # otherwise Sphinx warns "image file not readable".
        image_name = f"__{doc.module_name}.png"
        if not os.path.exists("/".join(doc_dir) + f"/{image_name}"):
            image_name = None
        rst = generate_rst(doc, module_def, image_name)
        output_filename = "/".join(doc_dir) + f"/{doc.module_name}.rst"
        os.makedirs(os.path.dirname(output_filename), exist_ok=True)
        with open(output_filename, "w") as f_output:
            f_output.write(rst) 

def generate_svg_file(input_filename):
    doc_dir = __file__.split("/")[:-2]
    doc_dir.extend(["source", "verilog"])
    os.makedirs("/".join(doc_dir), exist_ok=True)

    cmd = [
        'symbolator',
        '-i', input_filename,
        '-t',
        '-o', "/".join(doc_dir) + f"/",
        '-f', 'PNG'
    ]
    p = Popen(cmd, stdout=PIPE, stdin=PIPE, stderr=PIPE)
    p.communicate()

def generate_index_rst(files):
    """
    Generate/update the Verilog modules index.rst file with all generated modules.

    This function creates a Sphinx toctree that includes all Verilog module documentation
    files, allowing them to be properly indexed in the documentation.

    Args:
        files: List of Verilog filenames (e.g., ['adder.v', 'multiplier.v'])
    """
    docstring = ""
    docstring += "Verilog Modules\n"
    docstring += "===============\n\n"
    docstring += ".. toctree::\n"
    docstring += "    :maxdepth: 2\n"
    docstring += "    :caption: Modules:\n\n"

    # Extract module names from filenames and sort them
    module_names = sorted([os.path.splitext(file)[0] for file in files])

    for module_name in module_names:
        docstring += f"    {module_name}\n"

    doc_dir = __file__.split("/")[:-2]
    doc_dir.extend(["source", "verilog"])
    output_filename = "/".join(doc_dir) + "/index.rst"
    os.makedirs(os.path.dirname(output_filename), exist_ok=True)

    with open(output_filename, "w") as f_output:
        f_output.write(docstring)

    logger.info(f"Generated Verilog modules index with {len(module_names)} modules at {output_filename}")

if __name__ == "__main__":
    hdl_dir = __file__.split("/")[:-3]
    hdl_dir.extend(["hdl"])
    hdl_dir = "/".join(hdl_dir)
    generated_doc_files = []

    for root, dirs, files in os.walk(hdl_dir):
        for filename in sorted(files):
            if filename.endswith(".v"):
                # Generate the symbol image first, so that generate_rst_file() can
                # check whether it exists. This is optional - don't fail if it doesn't work.
                try:
                    generate_svg_file(os.path.join(root, filename))
                except Exception as e:
                    logger.debug(f"Could not generate SVG for {filename}: {e}")

                # Generate RST (this is critical - file must be generated)
                try:
                    generate_rst_file(os.path.join(root, filename))
                    generated_doc_files.append(filename)
                except Exception as e:
                    warnings.warn(f"Error processing {filename}: {e}")
                    logger.debug(f"{e}")
                    continue

    # Always generate index with the files that were successfully processed
    generate_index_rst(generated_doc_files)