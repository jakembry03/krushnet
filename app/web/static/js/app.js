console.log("KRUSHNET JAVASCRIPT LOADED");

async function updateBackendStatus() {
    const response = await fetch("/api/status");
    const data = await response.json();
    console.log(data);
}

updateBackendStatus();