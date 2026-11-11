document.addEventListener('DOMContentLoaded', () => {
    fetchComplaints();

    const form = document.getElementById('complaintForm');
    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const clientNameInput = document.getElementById('clientName');
            const categoryInput = document.getElementById('category');
            const descriptionInput = document.getElementById('description');

            const payload = {
                client_name: clientNameInput.value.trim(),
                category: categoryInput.value,
                description: descriptionInput.value.trim()
            };

            try {
                const response = await fetch('/api/complaints', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(payload)
                });

                if (response.ok) {
                    form.reset();
                    fetchComplaints();
                } else {
                    const errData = await response.json();
                    console.error('Server error:', errData);
                }
            } catch (error) {
                console.error('Network error:', error);
            }
        });
    }

    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            const searchTerm = e.target.value.toLowerCase();
            const rows = document.querySelectorAll('#complaintsTable tbody tr');
            
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(searchTerm) ? '' : 'none';
            });
        });
    }
});

async function fetchComplaints() {
    try {
        const response = await fetch('/api/complaints');
        const complaints = await response.json();
        
        const tbody = document.querySelector('#complaintsTable tbody');
        if (!tbody) return;
        
        tbody.innerHTML = '';

        let pendingCount = 0;
        let resolvedCount = 0;

        complaints.forEach(item => {
            const clientName = item.client_name || item.clientName || 'N/A';
            const category = item.category || 'N/A';
            const description = item.description || 'N/A';
            const status = item.status || 'Në Pritje';

            if (status.toLowerCase().includes('zgjidhur')) {
                resolvedCount++;
            } else {
                pendingCount++;
            }

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="ps-4 fw-semibold text-muted">#${item.id}</td>
                <td class="fw-medium text-white">${escapeHtml(clientName)}</td>
                <td><span class="badge bg-dark border border-secondary text-info">${escapeHtml(category)}</span></td>
                <td class="text-secondary">${escapeHtml(description)}</td>
                <td class="text-center pe-4">
                    <span class="${status.toLowerCase().includes('zgjidhur') ? 'text-emerald' : 'text-amber'} fw-semibold">
                        ${escapeHtml(status)}
                    </span>
                </td>
            `;
            tbody.appendChild(tr);
        });

        const statTotal = document.getElementById('statTotal');
        const statPending = document.getElementById('statPending');
        const statResolved = document.getElementById('statResolved');

        if (statTotal) statTotal.textContent = complaints.length;
        if (statPending) statPending.textContent = pendingCount;
        if (statResolved) statResolved.textContent = resolvedCount;

    } catch (error) {
        console.error('Fetch error:', error);
    }
}

function escapeHtml(text) {
    if (!text) return '';
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}