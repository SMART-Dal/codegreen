#include "adapters/python_bridge_adapter.hpp"
#include <iostream>
#include <sstream>
#include <cstdlib>
#include <fstream>
#include <filesystem>
#include <unistd.h>  // For getpid()

namespace codegreen {

PythonBridgeAdapter::PythonBridgeAdapter(const std::string& language_id) : language_id_(language_id) {
    // Get the path to the instrumentation system
    auto exe_path = std::filesystem::canonical("/proc/self/exe").parent_path();
    // The binary is in bin/, and instrumentation is in bin/src/instrumentation
    instrumentation_path_ = exe_path / "src" / "instrumentation";
    
    std::cout << "Python instrumentation path: " << instrumentation_path_ << std::endl;
}

std::string PythonBridgeAdapter::get_language_id() const {
    return language_id_;
}

std::string get_extension_for_language(const std::string& lang) {
    if (lang == "python") return ".py";
    if (lang == "c") return ".c";
    if (lang == "cpp") return ".cpp";
    if (lang == "java") return ".java";
    if (lang == "javascript") return ".js";
    return ".txt";
}

std::unique_ptr<ASTNode> PythonBridgeAdapter::parse(const std::string& source_code) {
    // For now, return a simple AST node - this could be enhanced later
    auto root = std::make_unique<ASTNode>();
    root->type = "module";
    root->name = "root";
    root->start_line = 1;
    root->end_line = 1;  // Will be updated with actual line count
    root->start_column = 1;
    root->end_column = 1;
    return root;
}

std::vector<CodeCheckpoint> PythonBridgeAdapter::generate_checkpoints(const std::string& source_code) {
    std::vector<CodeCheckpoint> checkpoints;
    
    try {
        // Write source code to temp file with correct extension
        std::string ext = get_extension_for_language(language_id_);
        std::string temp_file = "/tmp/codegreen_temp_" + std::to_string(getpid()) + ext;
        std::ofstream temp_out(temp_file);
        temp_out << source_code;
        temp_out.close();
        
        // Call Python instrumentation system
        std::string python_script = instrumentation_path_.string() + "/bridge_analyze.py";
        std::string command = "python3 " + python_script + " " + temp_file;
        
        std::cout << "Calling Python instrumentation: " << command << std::endl;
        
        // Execute Python instrumentation
        FILE* pipe = popen(command.c_str(), "r");
        if (!pipe) {
            std::cerr << "Failed to call Python instrumentation system" << std::endl;
            std::filesystem::remove(temp_file);
            return checkpoints;
        }
        
        // Read the results
        char buffer[256];
        std::string result;
        while (fgets(buffer, sizeof(buffer), pipe) != nullptr) {
            result += buffer;
        }
        
        int status = pclose(pipe);
        if (status != 0) {
            std::cerr << "Python instrumentation failed with status: " << status << std::endl;
            std::cerr << "Output: " << result << std::endl;
        } else {
            // Parse the results and create checkpoints
            checkpoints = parse_python_results(result);
        }
        
        // Clean up temp file
        std::filesystem::remove(temp_file);
        
    } catch (const std::exception& e) {
        std::cerr << "Error in generate_checkpoints: " << e.what() << std::endl;
    }
    
    return checkpoints;
}

std::string PythonBridgeAdapter::instrument_code(const std::string& source_code, 
                                               const std::vector<CodeCheckpoint>& checkpoints) {
    try {
        // Write source code to temp file
        std::string ext = get_extension_for_language(language_id_);
        std::string temp_file = "/tmp/codegreen_temp_" + std::to_string(getpid()) + ext;
        std::ofstream temp_out(temp_file);
        temp_out << source_code;
        temp_out.close();
        
        // Call Python instrumentation system to instrument the code
        std::string python_script = instrumentation_path_.string() + "/bridge_instrument.py";
        std::string command = "python3 " + python_script + " " + temp_file;
        
        std::cout << "Calling Python instrumentation for code generation: " << command << std::endl;
        
        // Execute Python instrumentation
        FILE* pipe = popen(command.c_str(), "r");
        if (!pipe) {
            std::cerr << "Failed to call Python instrumentation system" << std::endl;
            std::filesystem::remove(temp_file);
            return source_code; // Return original code on failure
        }
        
        // Read the instrumented code
        std::string instrumented_code;
        char buffer[256];
        while (fgets(buffer, sizeof(buffer), pipe) != nullptr) {
            instrumented_code += buffer;
        }
        
        int status = pclose(pipe);
        if (status != 0) {
            std::cerr << "Python instrumentation failed with status: " << status << std::endl;
            return source_code; // Return original code on failure
        }
        
        // Clean up temp file
        std::filesystem::remove(temp_file);
        
        return instrumented_code;
        
    } catch (const std::exception& e) {
        std::cerr << "Error in instrument_code: " << e.what() << std::endl;
        return source_code; // Return original code on failure
    }
}

bool PythonBridgeAdapter::analyze(const std::string& source_code) {
    // Simple analysis - could be enhanced
    return !source_code.empty();
}

std::vector<std::string> PythonBridgeAdapter::get_suggestions() const {
    return {"Consider using list comprehensions for better performance",
            "Profile memory usage in loops",
            "Use context managers for resource management"};
}

std::vector<std::string> PythonBridgeAdapter::get_file_extensions() const {
    if (language_id_ == "python") return {".py", ".pyw"};
    if (language_id_ == "c") return {".c", ".h"};
    if (language_id_ == "cpp") return {".cpp", ".hpp", ".cc", ".cxx"};
    if (language_id_ == "java") return {".java"};
    if (language_id_ == "javascript") return {".js", ".ts"};
    return {};
}

std::vector<CodeCheckpoint> PythonBridgeAdapter::parse_python_results(const std::string& output) {
    std::vector<CodeCheckpoint> checkpoints;
    std::stringstream ss(output);
    std::string line;
    
    while (std::getline(ss, line)) {
        if (line.find("POINT|") == 0) {
            std::stringstream line_ss(line);
            std::string part;
            std::vector<std::string> parts;
            
            while (std::getline(line_ss, part, '|')) {
                parts.push_back(part);
            }
            
            if (parts.size() >= 6) {
                CodeCheckpoint checkpoint;
                checkpoint.id = parts[1];
                checkpoint.type = parts[2];
                checkpoint.name = parts[3];
                checkpoint.line_number = std::stoul(parts[4]);
                checkpoint.column_number = std::stoul(parts[5]);
                checkpoint.context = "Auto-generated from Python instrumentation";
                checkpoints.push_back(checkpoint);
            }
        }
    }
    
    return checkpoints;
}

} // namespace codegreen