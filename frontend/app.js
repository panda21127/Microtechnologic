const listEl = document.getElementById('list');
const statusEl = document.getElementById('status');
const formEl = document.getElementById('create-form');

async function handleResponse(response) {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`HTTP ${response.status}: ${text}`);
  }
  return response.json();
}

async function loadShipments() {
  statusEl.textContent = 'Загрузка...';
  try {
    const shipments = await fetch('/api/shipments').then(handleResponse);
    render(shipments);
    statusEl.textContent = shipments.length ? '' : 'Список пуст';
  } catch (error) {
    statusEl.textContent = error.message;
  }
}

function render(shipments) {
  listEl.innerHTML = '';
  for (const shipment of shipments) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${shipment.id}</td>
      <td>${shipment.order_id}</td>
      <td>${shipment.destination}</td>
      <td>${shipment.status}</td>
      <td></td>
    `;
    const actionCell = tr.querySelector('td:last-child');
    if (shipment.status === 'created') {
      const button = document.createElement('button');
      button.textContent = 'Отправить';
      button.addEventListener('click', async () => {
        try {
          await fetch(`/api/shipments/${shipment.id}/dispatch`, {
            method: 'POST'
          }).then(handleResponse);
          await loadShipments();
        } catch (error) {
          statusEl.textContent = error.message;
        }
      });
      actionCell.appendChild(button);
    }
    listEl.appendChild(tr);
  }
}

formEl.addEventListener('submit', async (event) => {
  event.preventDefault();
  const data = new FormData(formEl);
  const payload = {
    order_id: data.get('order_id'),
    destination: data.get('destination')
  };
  statusEl.textContent = 'Создание...';
  try {
    await fetch('/api/shipments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(handleResponse);
    formEl.reset();
    await loadShipments();
  } catch (error) {
    statusEl.textContent = error.message;
  }
});

loadShipments();