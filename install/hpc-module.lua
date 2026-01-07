-- CodeGreen HPC Environment Module
-- Place this file in your HPC module directory (e.g., /usr/local/modules/codegreen/1.0.lua)

help([[
CodeGreen - Energy-aware software development tool
Measures energy consumption of code with fine-grained analysis

For more information: https://github.com/SMART-Dal/codegreen
]])

whatis("Name: CodeGreen")
whatis("Version: 1.0")
whatis("Category: Development Tools")
whatis("Description: Energy measurement and profiling tool")
whatis("Keywords: energy, profiling, sustainability, performance")

-- Set up environment
local codegreen_root = "/usr/local/codegreen"
local codegreen_bin = pathJoin(codegreen_root, "bin")

-- Add to PATH
prepend_path("PATH", codegreen_bin)

-- Python path for CLI
prepend_path("PYTHONPATH", codegreen_root)

-- Set environment variables
setenv("CODEGREEN_ROOT", codegreen_root)
setenv("CODEGREEN_HPC_MODE", "1")

-- Module dependencies
depends_on("python/3.8+")

-- Check for required permissions on load
if (mode() == "load") then
    -- Check if user has access to energy monitoring
    local powercap_test = capture("test -r /sys/class/powercap/intel-rapl:0/energy_uj 2>/dev/null && echo 'accessible' || echo 'denied'")
    if (powercap_test == "denied\n") then
        LmodMessage("Warning: Energy monitoring files not accessible.")
        LmodMessage("Contact your HPC administrator to join the 'powercap' group.")
        LmodMessage("Command: sudo usermod -a -G powercap $USER")
    end
end

-- Usage information
if (myModuleUserlvl() >= 2) then
    LmodMessage("CodeGreen loaded. Usage examples:")
    LmodMessage("  codegreen benchmark cpu_stress --duration 10")
    LmodMessage("  python -m codegreen.cli info")
end