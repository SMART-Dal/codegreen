FROM ubuntu:22.04

# Install dependencies
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-dev \
    build-essential cmake \
    libjsoncpp-dev libcurl4-openssl-dev libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy source code
COPY . .

# Install Python dependencies
RUN pip3 install -r requirements.txt

# Build C++ components
RUN mkdir build && cd build && \
    cmake .. -DCMAKE_BUILD_TYPE=Release && \
    make -j$(nproc)

# Install Python package
RUN pip3 install -e .

# Set entry point
ENTRYPOINT ["codegreen"]
