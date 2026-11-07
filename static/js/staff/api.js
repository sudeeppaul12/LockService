
const mockRequests = [
    {
        id: 1,
        customer: "John Smith",
        vehicle: "2020 Toyota Camry",
        serviceType: "Oil Change",
        preferredDate: "2026-11-10",
        status: "Requested",
        description: "Routine oil change and inspection."
    },
    {
        id: 2,
        customer: "Maria Garcia",
        vehicle: "2019 Honda Civic",
        serviceType: "Brake Inspection",
        preferredDate: "2026-11-12",
        status: "Requested",
        description: "Brakes are making a squeaking noise."
    },
    {
        id: 3,
        customer: "David Lee",
        vehicle: "2022 Ford F-150",
        serviceType: "Engine Diagnostics",
        preferredDate: "2026-11-14",
        status: "Requested",
        description: "Check engine light is on."
    }
];

// Temporary implementation.
// Later, this function will communicate with Flask.
export async function getServiceRequests() {
    return mockRequests;
}

export async function updateServiceRequest(id, changes) {
    const request = mockRequests.find(request => request.id === id);

    if (!request) {
        throw new Error("Request not found");
    }

    Object.assign(request, changes);

    return request;
}