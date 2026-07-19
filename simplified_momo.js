// Simplified JavaScript for MoMo payment - single date field approach

// Set default due date when plan is selected
const planSelect = document.querySelector('select[name="plan"]');
if (planSelect) {
    planSelect.addEventListener('change', function() {
        if (this.value) {
            // Get the selected plan's duration from data attribute
            const selectedOption = this.options[this.selectedIndex];
            const durationDays = parseInt(selectedOption.getAttribute('data-duration')) || 30;
            
            const today = new Date();
            const dueDate = new Date();
            dueDate.setDate(today.getDate() + durationDays);
            
            const dueDateInput = document.getElementById('f_due_date');
            if (dueDateInput && !dueDateInput.value) {
                const formattedDate = dueDate.toISOString().split('T')[0];
                dueDateInput.value = formattedDate;
            }
        }
    });
}

// Load existing MoMo data when editing a client
function openEditClientModal(btn) {
    const row = btn.closest('tr');
    const id = row.dataset.id;
    document.getElementById('modalTitle').innerText = "Modifier Client";
    document.getElementById('planLabel').innerText = "Abonnement";
    clientForm.action = `/business/zones/{{ zone.pk }}/clients/${id}/edit/`;
    
    document.getElementById('f_username').value = row.dataset.username;
    document.getElementById('f_email').value = row.dataset.email;
    document.getElementById('f_phone').value = row.dataset.phone;
    document.getElementById('f_phone2').value = row.dataset.phone2;
    
    document.getElementById('f_quartier').value = row.dataset.quartierId || "";
    document.getElementById('f_address').value = row.dataset.address;
    
    // Set plan selection if available
    const planSelect = clientForm.querySelector('select[name="plan"]');
    if (planSelect) {
        planSelect.value = row.dataset.planId || "";
    }
    
    // Set due date if available
    const dueDateInput = document.getElementById('f_due_date');
    if (dueDateInput && row.dataset.subscriptionEndDate) {
        dueDateInput.value = row.dataset.subscriptionEndDate;
    }
    
    // Set MoMo payment checkbox if client uses MoMo
    const momoCheckbox = document.getElementById('f_uses_momo');
    if (momoCheckbox && (row.dataset.usesMomoPayment === 'True' || row.dataset.usesMomoPayment === 'true')) {
        momoCheckbox.checked = true;
    }
    
    clientModal.classList.remove('hidden');
}