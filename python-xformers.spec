%undefine _debugsource_packages

# One HIP subpackage per ISA. Compiling every gfx into one hipcc
# (10 --offload-arch) OOMs and takes weeks; one arch per job is
# small enough for ninja -j$nproc.
%global hip_archs gfx906 gfx908 gfx90a gfx942 gfx1030 gfx1100 gfx1101 gfx1102 gfx1200 gfx1201
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
add AOT CK flash-attention for one target ISA. Every builder compiles
every ISA; pick the subpackage for the GPU that will run the code
(gfx1100 on a 7900 box, gfx942 on MI300, ...). The installed RPM is
what counts, not rocminfo on the builder. If several gfx* packages
are installed, the loader matches the live device; XFORMERS_HIP_ARCH
overrides.

# One subpackage per gfx. %%1 = ISA, %%2 = short GPU hint (no spaces).
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

%xformers_gfx gfx906 Vega20/MI50
%xformers_gfx gfx908 CDNA1/MI100
%xformers_gfx gfx90a CDNA2/MI200
%xformers_gfx gfx942 CDNA3/MI300
%xformers_gfx gfx1030 RDNA2/RX6800
%xformers_gfx gfx1100 RDNA3/RX7900
%xformers_gfx gfx1101 RDNA3/RX7800
%xformers_gfx gfx1102 RDNA3/RX7600
%xformers_gfx gfx1200 RDNA4/RX9070
%xformers_gfx gfx1201 RDNA4/RX9070XT

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
