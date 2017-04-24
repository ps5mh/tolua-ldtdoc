# -*- coding: utf-8 -*-
import re
import os

# i gave up (T_T)
override = {
	"System.Array": {
		"ToTable": {
			"return_type": "#list<System_Object#Object>"
		}
	}
}

# this parser can't handle these files yet
ignore_files = [
	"LuaInterface_LuaOutWrap.cs", 
	"System_Collections_Generic_DictionaryWrap.cs", 
	"System_Collections_Generic_Dictionary_KeyCollectionWrap.cs",
	"System_Collections_Generic_Dictionary_ValueCollectionWrap.cs",
	"System_Collections_Generic_KeyValuePairWrap.cs",
	"System_Collections_Generic_ListWrap.cs",
	"System_Collections_ObjectModel_ReadOnlyCollectionWrap.cs"]

builtin_types_map = {
	"int": "#number",
	"number": "#number",
	"string": "#string",
	"bool": "#boolean",
	"boolean": "#boolean",
	"float": "#number",
	"integer": "#number",
	"ushort": "#number",
	"sbyte": "#number",
	"unit": "#number",
	"byte": "#number",
	"long": "#number",
	"lightuserdata": "#number"
}

def get_class_name_from_file_name(ifile):
	file_name = os.path.basename(ifile)
	if file_name.endswith("Wrap.cs"):
		return file_name[:-7].replace("_",".")

def cstype_map_to_ldttype(cs_type):
	ldt_type = None
	if cs_type is not None:
		if cs_type in builtin_types_map:
			ldt_type = builtin_types_map[cs_type]
		elif cs_type.endswith("[]"):
			cs_type = cs_type[:-2]
			ldt_type = "System_Array#Array"
		else:
			module = cs_type.replace(".","_")
			_type = cs_type.split(".")[-1]
			ldt_type = module + "#" + _type
	return ldt_type

def parse(ifile,odir):
	parsing_class = None
	function_defs = {}
	filed_defs = {}

	with open(ifile,encoding="utf-8",mode="r") as f:
		brace_level = 0
		cs_function_def_parsing_func_name = None
		cs_function_def_breace_level = -1
		cs_function_def_max_args = 0
		cs_function_def_min_args = 11
		cs_function_def_is_static = True
		cs_function_def_return_type = None
		for line in f:
			if line.find("{") > 0: brace_level = brace_level + 1
			if line.find("}") > 0: 
				brace_level = brace_level - 1
				if brace_level == cs_function_def_breace_level and cs_function_def_parsing_func_name is not None:
					# will out c# function
					def_func_name = cs_function_def_parsing_func_name
					if cs_function_def_parsing_func_name.startswith("_CreateUnityEngine_"):
						def_func_name = "New"
						cs_function_def_is_static = True
						cs_function_def_max_args = 0
						cs_function_def_return_type = parsing_class["name"]
					elif cs_function_def_parsing_func_name.startswith("get_"):
						def_func_name = cs_function_def_parsing_func_name[len("get_"):]

					if def_func_name in function_defs:
						function_def = function_defs[def_func_name]
						function_def["param_count"] = 0 if cs_function_def_min_args == 11 else cs_function_def_min_args
						function_def["return_type"] = cstype_map_to_ldttype(cs_function_def_return_type)
						function_def["is_static"] = cs_function_def_is_static
						function_def["valid"] = True
						override_class = override.get(parsing_class["name"], {})
						override_func_def = override_class.get(def_func_name, {})
						override_return_type = override_func_def.get("return_type", "")
						if override_return_type:
							function_defs[def_func_name]["return_type"] = override_return_type

					elif def_func_name in filed_defs:
						filed_def = filed_defs[def_func_name]
						filed_def["type"] = cstype_map_to_ldttype(cs_function_def_return_type)
						filed_def["valid"] = True
					cs_function_def_breace_level = -1

			if cs_function_def_breace_level >= 0:
				# in c# function
				cs_function_def_arg_match = re.search(r'count == (\d+)', line)
				argc = None
				if cs_function_def_arg_match: 
					argc = int(cs_function_def_arg_match.group(1))
				cs_function_def_arg_match = re.search(r'CheckArgsCount\(L, (\d+)\)', line)
				if cs_function_def_arg_match: 
					argc = int(cs_function_def_arg_match.group(1))
				if argc:
					if cs_function_def_max_args < argc:
						cs_function_def_max_args = argc
					if cs_function_def_min_args > argc:
						cs_function_def_min_args = argc
				cs_function_def_instance_method_match = re.search(r' obj = ', line)
				if cs_function_def_instance_method_match:
					cs_function_def_is_static = False
					if cs_function_def_max_args < 1:
						cs_function_def_max_args = 1

				if cs_function_def_return_type is None:
					cs_function_def_return_match = re.match(r'^\s*([^\s]+?) o = [^n].*;$', line)
					if cs_function_def_return_match is None:
						cs_function_def_return_match = re.match(r'^\s*(.*?) ret = .*;$', line)
					if cs_function_def_return_match is None:
						cs_function_def_return_match = re.match(r'^\s*LuaDLL\.lua_push(.*?)\(', line)
					# kinda bad
					if cs_function_def_return_match is None:
						try_match = re.match(r'^\s*ToLua\.Push\(L, (.*?)\)', line)
						if try_match is not None and try_match.group(1) != "ret":
							fs = try_match.group(1).split(".")
							fs = fs[:-1]
							k = ".".join(fs)
							cs_function_def_return_type = k

					if cs_function_def_return_match:
						cs_function_def_return_type = cs_function_def_return_match.group(1)
				continue

			class_def_match = re.match(r'^\s*L\.BeginClass\(typeof\((.*?)\), typeof\((.*?)[,\)]', line)
			if class_def_match:
				assert(parsing_class == None)
				parsing_class = {"name": get_class_name_from_file_name(ifile),
								 "parent": class_def_match.group(2)}

			class_def_match = re.match(r'^\s*L\.BeginClass\(typeof\((.*?)\), null[,\)]', line)
			if class_def_match:
				assert(parsing_class == None)
				parsing_class = {"name": get_class_name_from_file_name(ifile)}

			class_def_match = re.match(r'^\s*L\.BeginStaticLibs\("(.*?)"\)', line)
			if class_def_match:
				assert(parsing_class == None)
				parsing_class = {"name": get_class_name_from_file_name(ifile)}

			class_def_match = re.match(r'^\s*L\.BeginEnum\(typeof\((.*?)\)', line)
			if class_def_match:
				assert(parsing_class == None)
				parsing_class = {"name": class_def_match.group(1)}

			function_def_match = re.match(r'^\s*L\.RegFunction\("(.*?)"', line)
			if function_def_match: 
				function_name = function_def_match.group(1)
				function_defs[function_name] = {"name": function_name}

			field_def_match = re.match(r'^\s*L\.RegVar\("(.*?)"', line)
			if field_def_match:
				field_name = field_def_match.group(1)
				filed_defs[field_name] = {"name":field_name}

			cs_function_def_match = re.match(r'^\s*static int (.*?)\(', line)
			if cs_function_def_match:
				cs_function_def_parsing_func_name = cs_function_def_match.group(1)
				cs_function_def_breace_level = brace_level
				cs_function_def_max_args = 0
				cs_function_def_min_args = 11
				cs_function_def_is_static = True
				cs_function_def_return_type = None

		# output
		ldt_type = cstype_map_to_ldttype(parsing_class["name"])
		parsing_module = ldt_type.split("#")[0]
		parsing_type = ldt_type.split("#")[1]
		with open(os.path.join(odir,parsing_module+".doclua"),"w") as of:
			of.write("---\n")
			of.write("-- @module %s\n\n" % parsing_module)
			of.write("---\n")
			of.write("-- @type %s\n" % parsing_type)
			if "parent" in parsing_class:
				of.write("-- @extends %s\n" % cstype_map_to_ldttype(parsing_class["parent"]))
			of.write("\n")
			for _, func in function_defs.items():
				if not "valid" in func: continue
				of.write("---\n")
				of.write("-- @function [parent=#%s] %s\n" % (parsing_type, func["name"]))
				if not func["is_static"]:
					of.write("-- @param self\n")
				for i in range(func["param_count"] - (0 if func["is_static"] else 1)):
					of.write("-- @param arg%d\n" % i)
				if func["return_type"] is not None:
					of.write("-- @return %s\n" % func["return_type"])
				of.write("\n")
			for _, field in filed_defs.items():
				if not "valid" in field: continue
				of.write("---\n")
				_type = field["type"] + " " if field["type"] is not None else ""
				of.write("-- @field [parent=#%s] %s%s\n\n" % (parsing_type, _type, field["name"]))
			of.write("return nil\n")

if __name__ == "__main__":
	srcdir1 = r"D:\develop\projects\UnitySample-2DRoguelike-ToLua\Assets\Source\Generate"
	srcdir2 = r"D:\develop\projects\UnitySample-2DRoguelike-ToLua\Assets\3rd\tolua\ToLua\BaseType"
	destdir = r"D:\develop\projects\UnitySample-2DRoguelike-ToLua\modules\tolua-ldtdoc\generated_doclua"
	flist1 = [os.path.join(srcdir1,f) for f in os.listdir(srcdir1)]
	flist2 = [os.path.join(srcdir2,f) for f in os.listdir(srcdir2)]

	for fpath in flist1 + flist2:
		fname = os.path.basename(fpath)
		if fpath.endswith("Wrap.cs") and fname not in ignore_files:
			parse(fpath, destdir)

	# generate doclua for root module (ex: UnityEngine.doclua)
	root_module_to_fields = {} # {module_name: {field_name:{type: }, ...}, ...}
	for fpath in flist1 + flist2:
		module_name = get_class_name_from_file_name(fpath)
		if module_name:
			module_paths = module_name.split(".")
			if len(module_paths) == 2: # field directly under root module
				root_module, filed_name = module_paths[0], module_paths[1]
				root_module_fields = root_module_to_fields.setdefault(root_module,{})
				root_module_fields[filed_name] = {"type": cstype_map_to_ldttype(module_name)}
	for module,fields in root_module_to_fields.items():
		with open(os.path.join(destdir, module + ".doclua"),"w") as of:
			of.write("---\n-- @module %s\n\n" % module)
			for field, field_info in fields.items():
				of.write("---\n-- @field [parent=#%s] %s %s\n\n" % (module, field_info["type"], field))
			of.write("return nil\n")
