#include "plugin/hardware_plugin.hpp"

namespace codegreen {

class NvidiaGPUAdapter : public HardwarePlugin {
public:
    NvidiaGPUAdapter() = default;
    ~NvidiaGPUAdapter() override = default;

    std::string name() const override { return "NVIDIA GPU"; }
    std::unique_ptr<Measurement> get_measurement() const override { return nullptr; }
    bool init() override { return true; }
    void cleanup() override {}
    bool is_available() const override { return false; }
};

} // namespace codegreen
