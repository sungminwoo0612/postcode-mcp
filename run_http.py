from postcode_mcp.server import mcp

if __name__ == "__main__":
    mcp.run(
        transport="http",
        host="127.0.0.1",
        port=3334,
        path="/mcp",
    )