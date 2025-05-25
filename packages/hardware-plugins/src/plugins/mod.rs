mod intel_rapl;

pub use intel_rapl::IntelRAPLPlugin;

// Re-export all plugins
pub use self::intel_rapl::IntelRAPLPlugin; 