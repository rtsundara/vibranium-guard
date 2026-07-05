from mcp.server.fastmcp import FastMCP

mcp = FastMCP("DLP Policy Server")

@mcp.tool()
def check_policy(app_category: str) -> str:
    """Checks if the app category is Allowed or Blocked according to the policy list."""
    high_risk_categories = ["Webmail", "Text Sharing", "Cloud Storage", "Personal Storage"]
    if app_category in high_risk_categories:
        return "Blocked/High Risk"
    else:
        return "Corporate Approved/Allowed"

if __name__ == "__main__":
    mcp.run()
