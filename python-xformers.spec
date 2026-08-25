%undefine _debugsource_packages

# One HIP subpackage per ISA. Compiling every gfx into one hipcc
# (--offload-arch A --offload-arch B) OOMs; one arch per job is
# small enough for ninja -j$nproc.
#
# ISA list = clang amdgcn -mcpu=help ∩ device-lib
# oclc_isa_version_*.bc (not the builder's GPU). New families
# (gfx1500 / RDNA6, …) appear automatically when both LLVM and
# rocm-device-libs grow the matching files. %hip_archs_skip
# drops an ISA if CK cannot compile it yet.
%{lua:
local fallback = {"gfx906","gfx908","gfx90a","gfx942","gfx1030","gfx1100","gfx1101","gfx1102","gfx1200","gfx1201"}
local function exists(p)
	local f = io.open(p, "r")
	if f then f:close() return true end
	return false
end
local function isa_num(name)
	return tonumber(name:sub(4), 16) or 0
end
local function keep(name)
	if not name:match("^gfx[0-9a-f][0-9a-f][0-9a-f]+$") then return false end
	local rest = name:sub(4)
	local fam, minor
	if rest:match("^1[0-9]") and #rest >= 4 then
		fam = tonumber(rest:sub(1,2))
		minor = rest:sub(3)
	else
		fam = tonumber(rest:sub(1,1))
		minor = rest:sub(2)
	end
	if not fam or fam <= 8 then return false end
	if fam == 9 then
		if minor == "06" or minor == "08" or minor == "0a" or minor == "40" or minor == "41" or minor == "42" then return true end
		local first = minor:sub(1,1)
		return first == "5" or first == "6" or first == "7" or first == "8" or first == "9" or first == "a" or first == "b" or first == "c" or first == "d" or first == "e" or first == "f"
	end
	if fam == 10 then return name == "gfx1030" end
	if fam == 11 then return name == "gfx1100" or name == "gfx1101" or name == "gfx1102" end
	if fam == 12 then return name == "gfx1200" or name == "gfx1201" end
	return true
end
local skip = {}
for s in rpm.expand("%{?hip_archs_skip}"):gmatch("%S+") do skip[s] = true end
local clang = rpm.expand("%{_bindir}") .. "/clang"
if not exists(clang) then clang = "clang" end
local h = io.popen(clang .. " -target amdgcn-amd-amdhsa -mcpu=help 2>&1")
local out = h and (h:read("*a") or "") or ""
if h then h:close() end
local cpus = {}
for name in out:gmatch("gfx[0-9a-f][0-9a-f][0-9a-f]+") do
	cpus[name] = true
end
local bcdir = rpm.expand("%{_libdir}") .. "/amdgcn/bitcode"
local list = {}
for name, _ in pairs(cpus) do
	if keep(name) and not skip[name] and exists(bcdir .. "/oclc_isa_version_" .. name:sub(4) .. ".bc") then
		list[#list+1] = name
	end
end
if #list == 0 then list = fallback end
table.sort(list, function(a,b) return isa_num(a) < isa_num(b) end)
rpm.define("hip_archs " .. table.concat(list, " "))
}
# third_party/composable_kernel_tiled pin from xformers v0.0.35 (.gitmodules).
# The PyPI sdist omits it; cooker has no composable-kernel package.
%global ck_commit 50fad035248b154cdfa4505cf5de7465ce146149

Name:		python-xformers
Version:	0.0.35
Release:	2
Summary:	Hackable transformer building blocks
License:	BSD-3-Clause AND MIT
Group:		Development/Python
URL:		https://github.com/facebookresearch/xformers
Source0:	https://files.pythonhosted.org/packages/source/x/xformers/xformers-%{version}.tar.gz
Source1:	https://github.com/ROCm/composable_kernel/archive/%{ck_commit}.tar.gz#/composable_kernel-%{ck_commit}.tar.gz
# Not Patch0: the python buildsystem autosetup would apply it to Source0.
Source2:	0001-ck-tile-clang23-rdna.patch

BuildSystem:	python
BuildRequires:	cmake
BuildRequires:	ninja
BuildRequires:	clang
BuildRequires:	rocm-device-libs
BuildRequires:	pkgconfig(python)
BuildRequires:	python
BuildRequires:	python%{pyver}dist(pip)
BuildRequires:	python%{pyver}dist(setuptools)
BuildRequires:	python%{pyver}dist(wheel)
BuildRequires:	python%{pyver}dist(torch)
BuildRequires:	python%{pyver}dist(numpy)
BuildRequires:	hipcc
BuildRequires:	/usr/bin/clang-offload-bundler
BuildRequires:	cmake(hip)
BuildRequires:	cmake(rocthrust)
BuildRequires:	cmake(rocprim)
BuildRequires:	cmake(hipcub)
Requires:	python%{pyver}dist(torch)
Requires:	python%{pyver}dist(numpy)

%description
xFormers transformer building blocks. The base package is CPU (and
uses torch SDPA on any GPU). Optional python-xformers-gfx* packages
add AOT CK flash-attention for one target ISA. The ISA set is
whatever this build's clang and rocm-device-libs can actually
target (so a ROCm that adds gfx1500 grows a matching subpackage
on the next rebuild). Every builder compiles every detected ISA;
pick the subpackage for the GPU that will run the code (gfx1100
on a 7900 box, gfx942 on MI300, ...). The installed RPM is what
counts, not rocminfo on the builder. If several gfx* packages are
installed, the loader matches the live device; XFORMERS_HIP_ARCH
overrides.

# One subpackage per detected gfx. %%1 = ISA, %%2 = short GPU hint.
%define xformers_gfx() \
%package %1\
Summary:	HIP flash-attention for %1 (%2)\
Group:		Development/Python\
Requires:	python-xformers = %{EVRD}\
\
%description %1\
AOT Composable Kernel flash-attention for %1 (%2).\
Produced on every host architecture; install this on machines whose\
GPU is %1. The builder's GPU is irrelevant.\
\
%files %1\
%{python_sitearch}/xformers/_C_%1.so\
%{nil}

%{lua:
local hints = {
	gfx906 = "Vega20/MI50",
	gfx908 = "CDNA1/MI100",
	gfx90a = "CDNA2/MI200",
	gfx942 = "CDNA3/MI300",
	gfx950 = "CDNA4/MI350",
	gfx1030 = "RDNA2/RX6800",
	gfx1100 = "RDNA3/RX7900",
	gfx1101 = "RDNA3/RX7800",
	gfx1102 = "RDNA3/RX7600",
	gfx1200 = "RDNA4/RX9070",
	gfx1201 = "RDNA4/RX9070XT",
	gfx1310 = "RDNA3.5",
	gfx1500 = "RDNA6",
}
for a in string.gmatch(rpm.expand("%{hip_archs}"), "%S+") do
	print(rpm.expand("%xformers_gfx " .. a .. " " .. (hints[a] or "AMDGPU")))
end
}

%prep -a
# setup.py only enables HIP if torch.version.hip is set. Also honour
# HIP_ARCHITECTURES so a ROCm toolchain can be selected explicitly.
sed -i 's/torch.version.hip$/torch.version.hip or os.getenv("HIP_ARCHITECTURES")/' setup.py
# torch 2.13 AutogradState.h uses C++20 bit-field default initializers;
# hipcc -Werror turns the c++17 diagnostic into a hard error.
sed -i 's/-std=c++17/-std=c++20/g' setup.py
# clang 23 is stricter than the -Werror HIP flags xformers ships.
# -Wc++11-narrowing is a hard error here and trips on signed bf16.
sed -i '/"-Werror",/d; /"-Wc++11-narrowing",/d' setup.py
# Restore the CK Tile tree setup.py expects (PyPI sdist ships only cutlass).
tar xf %{SOURCE1}
rm -rf third_party/composable_kernel_tiled
mv composable_kernel-%{ck_commit} third_party/composable_kernel_tiled
# clang 23 rejects __host__/__device__ on deduction guides; RDNA wave32
# + headdim 256 divided by zero in the June 2025 FMHA bwd policy.
pushd third_party/composable_kernel_tiled
patch -p1 < %{SOURCE2}
popd
# Load the _C_<gfx>.so from the installed RPM. Builders have no
# target GPU: one gfx* package => that ISA; several => live device.
python - <<'PY'
from pathlib import Path
p = Path("xformers/_cpp_lib.py")
t = p.read_text()
old = '''    extfinder = importlib.machinery.FileFinder(lib_dir, loader_details)
    if torch.version.hip and not hasattr(torch.version, "git_version"):
        ext_specs = extfinder.find_spec("_C_hip")
    else:
        ext_specs = extfinder.find_spec("_C")
'''
new = '''    extfinder = importlib.machinery.FileFinder(lib_dir, loader_details)
    ext_specs = None
    gfx = os.environ.get("XFORMERS_HIP_ARCH", "").strip().split()[:1]
    gfx = gfx[0] if gfx else ""
    installed = []
    try:
        installed = sorted(
            n[3:-3]
            for n in os.listdir(lib_dir)
            if n.startswith("_C_gfx") and n.endswith(".so")
        )
    except OSError:
        installed = []
    if not gfx and len(installed) == 1:
        gfx = installed[0]
    if not gfx and len(installed) > 1 and getattr(torch.version, "hip", None) and torch.cuda.is_available():
        try:
            want = torch.cuda.get_device_properties(0).gcnArchName.split(":")[0]
            if want in installed:
                gfx = want
        except Exception:
            gfx = ""
    if gfx:
        ext_specs = extfinder.find_spec("_C_" + gfx)
    if ext_specs is None and torch.version.hip and not hasattr(torch.version, "git_version"):
        ext_specs = extfinder.find_spec("_C_hip")
    if ext_specs is None:
        ext_specs = extfinder.find_spec("_C")
'''
if old not in t:
    raise SystemExit("xformers/_cpp_lib.py loader block not found")
p.write_text(t.replace(old, new, 1))
PY

%build -p
export CC=clang
export CXX=clang++
export FORCE_CUDA=0
export BUILD_VERSION=%{version}
export TORCH_CUDA_ARCH_LIST=
export ROCM_PATH=%{_prefix}
export ROCM_HOME=%{_prefix}
export HIP_CLANG_PATH=%{_bindir}
export HIP_DEVICE_LIB_PATH=%{_libdir}/amdgcn/bitcode
# Default %%py_build is CPU-only (torch SDPA on any GPU).
export HIP_ARCHITECTURES=
export XFORMERS_CK_FLASH_ATTN=0
export MAX_JOBS=${RPM_BUILD_NCPUS:-$(nproc)}

%build -a
# One hipcc ISA at a time so ninja can use all cores without OOM.
mkdir -p hip-libs
export XFORMERS_CK_FLASH_ATTN=1
for gfx in %{hip_archs}; do
	rm -rf build hip-w hip-tmp
	export HIP_ARCHITECTURES="$gfx"
	export PYTORCH_ROCM_ARCH="$gfx"
	# pip wheel (pyproject) does not leave build/_C.so; pull it out of the wheel.
	python -m pip wheel --no-deps --no-build-isolation --verbose -w hip-w .
	python -c 'import glob,shutil,sys,zipfile,os; gfx=sys.argv[1]; ws=glob.glob("hip-w/*.whl");
assert ws, "no HIP wheel for "+gfx
z=zipfile.ZipFile(ws[0]); ns=[n for n in z.namelist() if n.endswith("_C.so")];
assert ns, "no _C.so in "+ws[0]
z.extract(ns[0],"hip-tmp"); os.makedirs("hip-libs",exist_ok=True)
shutil.move("hip-tmp/"+ns[0],"hip-libs/_C_%s.so"%gfx)' "$gfx"
done
# Leave a CPU tree so %%py_install packages the base module, not the last HIP build.
rm -rf build hip-w hip-tmp
export HIP_ARCHITECTURES=
export XFORMERS_CK_FLASH_ATTN=0

%install -a
install -m 755 hip-libs/_C_gfx*.so %{buildroot}%{python_sitearch}/xformers/

%files
%doc README.md
%license LICENSE
%{python_sitearch}/xformers
%exclude %{python_sitearch}/xformers/_C_gfx*.so
%{python_sitearch}/xformers-*.*-info
