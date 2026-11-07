
import { getServiceRequests} from "./api.js";
import {openAppointment} from "./appointments.js";

export async function initializeRequests() {
    const tableBody = document.getElementById("requests-table-body");

    if (!tableBody) {
        console.error("Requests table body not found.");
        return;
    }

    try {
        const requests = await getServiceRequests();
        renderRequests(tableBody, requests);
    } catch (error) {
        console.error("Unable to load requests:", error);
        tableBody.replaceChildren();

        const row = tableBody.insertRow();
        const cell = row.insertCell();
        cell.colSpan = 6;
        cell.textContent = "Unable to load service requests.";
    }
}

function renderRequests(tableBody, requests) {
    tableBody.replaceChildren();

    for (const request of requests) {
        const row = tableBody.insertRow();

        const values = [
            request.customer,
            request.vehicle,
            request.serviceType,
            request.preferredDate,
            request.status
        ];

        for (const value of values) {
            const cell = row.insertCell();
            cell.textContent = value ?? "";
        }

        const actionCell = row.insertCell();
        const reviewButton = document.createElement("button");

        reviewButton.type = "button";
        reviewButton.textContent = "Review";

        reviewButton.addEventListener("click", () => {
            openAppointment(request, initializeRequests);
        });

        actionCell.appendChild(reviewButton);
    }
}

