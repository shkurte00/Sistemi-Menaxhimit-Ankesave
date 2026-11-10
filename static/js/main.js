document.addEventListener('DOMContentLoaded', () => {
    loadComplaints();

    const form = document.getElementById('complaintForm');
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const clientName = document.getElementById('clientName').value;
        const category = document.getElementById('category').value;
        const description = document.getElementById('description').value;

        const data = {
            title: clientName,
            category_id: 1,
            description: description,
            priority: category 
        };

        try {
            const response = await fetch('/api/complaints', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });

            const result = await response.json();
            if (result.success) {
                form.reset();
                loadComplaints();
            } else {
                alert('Gabim: ' + result.message);
            }
        } catch (error) {
            console.error('Gabim në rrjet:', error);
        }
    });
});

async function loadComplaints() {
    try {
        const response = await fetch('/api/complaints');
        const result = await response.json();
        const tbody = document.getElementById('complaintsTableBody');
        
        if (result.success && result.data.length > 0) {
            tbody.innerHTML = '';
            result.data.forEach(c => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${c.id}</td>
                    <td>${c.title}</td>
                    <td>${c.priority || '-'}</td>
                    <td>${c.description}</td>
                    <td><span class="badge bg-warning text-dark">${c.status || 'Në pritje'}</span></td>
                `;
                tbody.appendChild(tr);
            });
        } else {
            tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted">Nuk ka ankesa të regjistruara.</td></tr>`;
        }
    } catch (error) {
        console.error('Gabim gjatë ngarkimit të ankesave:', error);
    }
}