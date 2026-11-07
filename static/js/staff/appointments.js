
import { updateServiceRequest } from "./api.js";

// Opens the Appointment Management section
export function openAppointment(request, refreshTable) {
    const section = document.getElementById("appointments");
    const details = document.getElementById("appointment-details");

    details.replaceChildren();

    const fields = [
        ["Customer", request.customer],
        ["Vehicle", request.vehicle],
        ["Service", request.serviceType],
        ["Preferred Date", request.preferredDate],
        ["Status", request.status],
        ["Problem", request.description]
    ];

    for (const [label, value] of fields) {
        const line = document.createElement("p");
        line.textContent = `${label}: ${value}`;
        details.appendChild(line);
    }

    let actions = [];

    if (request.status === "Requested") {
        actions = ["Confirm", "Reschedule", "Cancel"];
    } else if (request.status === "Scheduled") {
        actions = ["Reschedule", "Cancel"];
    }

    for (const action of actions) {
        const button = document.createElement("button");
        button.textContent = action;
        button.onclick = () => changeAppointment(request, action, refreshTable);
        details.appendChild(button);
    }

    const closeButton = document.createElement("button");
    closeButton.textContent = "Close";
    closeButton.onclick = () => section.hidden = true;
    details.appendChild(closeButton);

    section.hidden = false;
    section.scrollIntoView({ behavior: "smooth" });
}

// Updates an appointment through api.js
async function changeAppointment(request, action, refreshTable) {
    const changes = {};

    if (action === "Confirm") {
        changes.status = "Scheduled";
    }

    if (action === "Cancel") {
        if (!confirm("Cancel this request?")) return;
        changes.status = "Canceled";
    }

    //needs work to validate date input
    if (action === "Reschedule") {
        const date = prompt("New date (YYYY-MM-DD):", request.preferredDate);
        if (date === null) return;

        if (!/^\d{4}-\d{2}-\d{2}$/.test(date) ||
            Number.isNaN(new Date(date).getTime())) {
            alert("Enter a valid date.");
            return;
        }

        changes.preferredDate = date;
        changes.status = "Scheduled";
    }

    try {
        const updated = await updateServiceRequest(request.id, changes);
        await refreshTable();
        openAppointment(updated, refreshTable);
    } catch (error) {
        console.error(error);
        alert("Unable to update appointment.");
    }
}

document.querySelector('a[href="#appointments"]')?.addEventListener("click", () => {
    document.getElementById("appointments").hidden = false;
});