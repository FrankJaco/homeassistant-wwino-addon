import React, { useState, useEffect } from 'react';
import { Search, Plus, Minus, XCircle, ChevronDown, ChevronUp } from 'lucide-react'; // Using Lucide for icons
// Removed: import './index.css'; // This line caused the "Could not resolve" error

// Main App component
const App = () => {
    const [vivinoUrl, setVivinoUrl] = useState('');
    const [wines, setWines] = useState([]);
    const [filterName, setFilterName] = useState('');
    const [filterVintage, setFilterVintage] = useState('');
    const [message, setMessage] = useState('');
    const [messageType, setMessageType] = useState(''); // 'success' or 'error'
    const [isLoading, setIsLoading] = useState(false);

    // IMPORTANT: Set API_BASE_URL to '/api' so Nginx can correctly proxy requests
    // to the Flask backend running within the same addon container.
    const API_BASE_URL = '';

    // --- Message Handling ---
    const showMessage = (msg, type) => {
        setMessage(msg);
        setMessageType(type);
        setTimeout(() => {
            setMessage('');
            setMessageType('');
        }, 3000); // Message disappears after 3 seconds
    };

    // --- Fetch Wines from Backend ---
    const fetchWines = async () => {
        setIsLoading(true);
        try {
            const queryParams = new URLSearchParams();
            if (filterName) queryParams.append('name', filterName);
            if (filterVintage) queryParams.append('vintage', filterVintage);

            // Ensure API_BASE_URL is prepended to the endpoint
            const response = await fetch(`${API_BASE_URL}/inventory?${queryParams.toString()}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            // Sort by added_at descending so most recent are at the top
            const sortedData = data.sort((a, b) => new Date(b.added_at) - new Date(a.added_at));
            setWines(sortedData);
            showMessage('Inventory loaded successfully!', 'success');
        } catch (error) {
            console.error("Error fetching wines:", error);
            showMessage(`Error loading inventory: ${error.message}`, 'error');
        } finally {
            setIsLoading(false);
        }
    };

    // Fetch wines on component mount and when filters change
    useEffect(() => {
        fetchWines();
    }, [filterName, filterVintage]);

    // --- Scan Wine (Add/Increment) ---
    const handleScanWine = async () => {
        if (!vivinoUrl) {
            showMessage('Please enter a Vivino URL.', 'error');
            return;
        }

        setIsLoading(true);
        try {
            // Ensure API_BASE_URL is prepended to the endpoint
            const response = await fetch(`${API_BASE_URL}/scan-wine`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ vivino_url: vivinoUrl }),
            });

            const data = await response.json();
            if (response.ok) {
                showMessage(`Successfully scanned and added/updated ${data.wine_name} (Quantity: ${data.quantity_added}).`, 'success');
                setVivinoUrl(''); // Clear input after successful scan
                fetchWines(); // Refresh inventory
            } else {
                throw new Error(data.message || 'Failed to scan wine.');
            }
        } catch (error) {
            console.error("Error scanning wine:", error);
            showMessage(`Failed to scan wine: ${error.message}`, 'error');
        } finally {
            setIsLoading(false);
        }
    };

    // --- Delete Wine ---
    const handleDeleteWine = async (url) => {
        // IMPORTANT: Replaced window.confirm with a custom modal/message box in a real app
        // For this context, keeping it as is per previous conversation.
        if (!window.confirm("Are you sure you want to delete this wine entry?")) {
            return;
        }

        setIsLoading(true);
        try {
            // Ensure API_BASE_URL is prepended to the endpoint
            const response = await fetch(`${API_BASE_URL}/inventory/wine`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ vivino_url: url }),
            });

            const data = await response.json();
            if (response.ok) {
                showMessage(`Wine deleted successfully: ${data.message}.`, 'success');
                fetchWines(); // Refresh inventory
            } else {
                throw new Error(data.message || 'Failed to delete wine.');
            }
        } catch (error) {
            console.error("Error deleting wine:", error);
            showMessage(`Failed to delete wine: ${error.message}`, 'error');
        } finally {
            setIsLoading(false);
        }
    };

    // --- Set Wine Quantity ---
    const handleSetQuantity = async (url, newQuantity) => {
        if (newQuantity < 0 || !Number.isInteger(newQuantity)) {
            showMessage('Quantity must be a non-negative integer.', 'error');
            return;
        }

        setIsLoading(true);
        try {
            // Ensure API_BASE_URL is prepended to the endpoint
            const response = await fetch(`${API_BASE_URL}/inventory/wine/set_quantity`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ vivino_url: url, quantity: newQuantity }),
            });

            const data = await response.json();
            if (response.ok) {
                showMessage(`Quantity set to ${newQuantity}.`, 'success');
                fetchWines(); // Refresh inventory
            } else {
                throw new Error(data.message || 'Failed to set quantity.');
            }
        } catch (error) {
            console.error("Error setting quantity:", error);
            showMessage(`Failed to set quantity: ${error.message}`, 'error');
        } finally {
            setIsLoading(false);
        }
    };

    // --- Consume Wine (Decrement Quantity) ---
    const handleConsumeWine = async (url, currentQuantity) => {
        if (currentQuantity <= 0) {
            showMessage('Cannot consume, quantity is already zero.', 'error');
            return;
        }
        // IMPORTANT: Replaced window.confirm with a custom modal/message box in a real app
        // For this context, keeping it as is per previous conversation.
        if (!window.confirm(`Are you sure you want to consume one bottle of this wine? Current: ${currentQuantity}`)) {
            return;
        }

        setIsLoading(true);
        try {
            // Ensure API_BASE_URL is prepended to the endpoint
            const response = await fetch(`${API_BASE_URL}/inventory/wine/consume`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ vivino_url: url, quantity: 1 }), // Always consume 1 for now
            });

            const data = await response.json();
            if (response.ok) {
                // The backend now sends 'new_quantity' in the success response for consume
                showMessage(`Wine consumed. New quantity: ${data.new_quantity}.`, 'success');
                fetchWines(); // Refresh inventory
            } else {
                throw new Error(data.message || 'Failed to consume wine.');
            }
        } catch (error) {
            console.error("Error consuming wine:", error);
            showMessage(`Failed to consume wine: ${error.message}`, 'error');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-gray-100 p-4 font-sans flex flex-col items-center">
            <div className="w-full max-w-4xl bg-white shadow-lg rounded-xl p-6 space-y-6">
                <h1 className="text-4xl font-bold text-center text-gray-800 mb-6">Wonderful Wino Inventory</h1>

                {/* Message display */}
                {message && (
                    <div className={`p-3 rounded-md text-center ${messageType === 'success' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'} transition-opacity duration-300`}>
                        {message}
                    </div>
                )}

                {/* Scan Wine Section */}
                <div className="flex flex-col md:flex-row items-center space-y-4 md:space-y-0 md:space-x-4">
                    <input
                        type="text"
                        placeholder="Enter Vivino URL to scan new wine"
                        value={vivinoUrl}
                        onChange={(e) => setVivinoUrl(e.target.value)}
                        className="flex-grow p-3 border border-gray-300 rounded-lg shadow-sm focus:ring-blue-500 focus:border-blue-500 text-gray-700 w-full"
                    />
                    <button
                        onClick={handleScanWine}
                        disabled={isLoading}
                        className="px-6 py-3 bg-blue-600 text-white font-semibold rounded-lg shadow-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-75 transition-all duration-200 w-full md:w-auto"
                    >
                        {isLoading ? 'Scanning...' : 'Scan Wine'}
                    </button>
                </div>

                {/* Filters Section */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="flex items-center space-x-2 p-3 border border-gray-300 rounded-lg shadow-sm bg-gray-50">
                        <Search className="text-gray-500" size={20} />
                        <input
                            type="text"
                            placeholder="Filter by Name"
                            value={filterName}
                            onChange={(e) => setFilterName(e.target.value)}
                            className="flex-grow bg-transparent outline-none text-gray-700"
                        />
                    </div>
                    <div className="flex items-center space-x-2 p-3 border border-gray-300 rounded-lg shadow-sm bg-gray-50">
                        <Search className="text-gray-500" size={20} />
                        <input
                            type="number"
                            placeholder="Filter by Vintage"
                            value={filterVintage}
                            onChange={(e) => setFilterVintage(e.target.value)}
                            className="flex-grow bg-transparent outline-none text-gray-700"
                        />
                    </div>
                </div>

                {/* Wine List */}
                <div className="space-y-4">
                    <h2 className="text-3xl font-semibold text-gray-800 pt-4 pb-2 border-b border-gray-200">Your Wine Inventory</h2>
                    {wines.length === 0 && !isLoading ? (
                        <p className="text-center text-gray-500">No wines in inventory. Scan one to get started!</p>
                    ) : (
                        wines.map((wine) => (
                            <div key={wine.vivino_url} className="flex flex-col md:flex-row items-start md:items-center bg-gray-50 p-4 rounded-lg shadow-sm hover:shadow-md transition-shadow duration-200 space-y-4 md:space-y-0 md:space-x-4">
                                <img
                                    src={wine.image_url || `https://placehold.co/100x150/aabbcc/ffffff?text=No+Image`}
                                    alt={wine.name}
                                    className="w-24 h-36 object-cover rounded-md flex-shrink-0 mx-auto md:mx-0"
                                    onError={(e) => { e.target.onerror = null; e.target.src = `https://placehold.co/100x150/aabbcc/ffffff?text=No+Image`; }}
                                />
                                <div className="flex-grow text-gray-700 text-center md:text-left">
                                    <h3 className="text-xl font-bold text-gray-900">{wine.name} ({wine.vintage || 'N/A'})</h3>
                                    <p className="text-sm">
                                        <span className="font-medium">Type:</span> {wine.varietal || 'N/A'} |
                                        <span className="font-medium"> Region:</span> {wine.region || 'N/A'}, {wine.country || 'N/A'}
                                    </p>
                                    <p className="text-sm">
                                        <span className="font-medium">Vivino Rating:</span> {wine.vivino_rating || 'N/A'} ({wine.vivino_num_ratings || '0'} ratings) |
                                        <span className="font-medium"> Price:</span> {wine.price_usd ? `$${wine.price_usd.toFixed(2)}` : 'N/A'}
                                    </p>
                                    <p className="text-sm text-gray-500">Added: {new Date(wine.added_at).toLocaleDateString()}</p>
                                </div>
                                <div className="flex items-center space-x-2 flex-shrink-0 mx-auto md:mx-0">
                                    <span className="text-lg font-bold text-gray-800">Qty: {wine.quantity}</span>
                                    <button
                                        onClick={() => handleSetQuantity(wine.vivino_url, wine.quantity + 1)}
                                        className="p-2 rounded-full bg-green-200 text-green-800 hover:bg-green-300 transition-colors duration-200 shadow-sm"
                                        aria-label="Increment quantity"
                                    >
                                        <Plus size={18} />
                                    </button>
                                    <button
                                        onClick={() => handleConsumeWine(wine.vivino_url, wine.quantity)}
                                        className="p-2 rounded-full bg-red-200 text-red-800 hover:bg-red-300 transition-colors duration-200 shadow-sm"
                                        aria-label="Consume one"
                                    >
                                        <Minus size={18} />
                                    </button>
                                    <button
                                        onClick={() => handleDeleteWine(wine.vivino_url)}
                                        className="p-2 rounded-full bg-gray-200 text-gray-600 hover:bg-gray-300 transition-colors duration-200 shadow-sm"
                                        aria-label="Delete wine"
                                    >
                                        <XCircle size={18} />
                                    </button>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>
        </div>
    );
};

export default App;
