// Chat UI
const chat = document.getElementById('chat');
const form = document.getElementById('form');
const input = document.getElementById('input');
const weightInput = document.getElementById('weight');

function appendMsg(text, role) {
    const div = document.createElement('div');
    div.className = 'msg ' + (role === 'user' ? 'user' : 'bot');
    div.textContent = text;
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
}

// Initial message
appendMsg('Hi! Ask food (chicken 150g)', 'bot');

form.addEventListener('submit', async e => {
    e.preventDefault();
    const q = input.value.trim();
    const w = weightInput.value.trim();
    if (!q) return;
    appendMsg(w ? q + ' ' + w + 'g' : q, 'user');
    input.value = '';
    weightInput.value = '';
    try {
        const res = await fetch('/api/nutrition', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                query: q,
                weight_g: w ? parseInt(w) : undefined
            })
        });
        const data = await res.json();
        if (!data.ok) {
            appendMsg(data.message || 'Food not found', 'bot')
        } else {
            appendMsg(`${data.matched_name} (${data.weight_g}g)\nCalories:${data.calories} Protein:${data.protein} Carbs:${data.carbs} Fat:${data.fat}`, 'bot')
        }
    } catch (err) {
        appendMsg('Network/server error', 'bot')
    }
});
