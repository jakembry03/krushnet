console.log("KRUSHNET JAVASCRIPT LOADED");

async function updateBackendStatus() {
    console.log("1. updateBackendStatus started");
    const response = await fetch("/api/status");
    console.log("2. FastAPI responded");
    console.log("HTTP status:", response.status);
    const data = await response.json();
    console.log("3. JSON received:");
    console.log(data);
    const statusText = document.getElementById("status-text");
    console.log("4. HTML element found:");
    console.log(statusText)
    statusText.textContent = "Backend Online";
    console.log("5. Text Changed");

}

updateBackendStatus();