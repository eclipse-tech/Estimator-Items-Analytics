const express = require('express');
const path = require('path');

const app = express();
const PORT = 2999;

// Serve static files at /estimator-ui path
app.use('/estimator-ui', express.static(path.join(__dirname)));

// Redirect root to /estimator-ui
app.get('/', (req, res) => {
    res.redirect('/estimator-ui');
});

// Fallback to index.html for /estimator-ui
app.get('/estimator-ui', (req, res) => {
    res.sendFile(path.join(__dirname, 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
    console.log(`✅ Frontend server running at http://localhost:${PORT}/estimator-ui`);
});
