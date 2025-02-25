import type React from "react";
import { useState } from "react";

const App: React.FC = () => {
    const [isEnter, setIsEnter] = useState(false);
    const [error, setError] = useState("");
    const [file, setFile] = useState<File | null>(null);
    const [isTranslate, setIsTranslate] = useState(false);
    const [isLoading, setIsLoading] = useState(false);

    const apiBaseUrl = import.meta.env.VITE_LEADABLE_API_URL || "http://localhost:8000";

    const dragEnter = () => {
        setIsEnter(true);
    };

    const dragLeave = () => {
        setIsEnter(false);
    };

    const dropFile = (e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        setIsEnter(false);
        const uploadedFile = e.dataTransfer.files[0];
        if (uploadedFile.type !== "application/pdf") {
            setError("Please upload a pdf file");
            return;
        }
        setFile(uploadedFile);
        setError("");
        console.log(uploadedFile);
    };

    const translate = async () => {
        if (!file) {
            setError("Please upload a file");
            return;
        }
        if (file.type !== "application/pdf") {
            setError("Please upload a pdf file");
            return;
        }

        const formData = new FormData();
        formData.append("file", file);

        setIsLoading(true);
        try {
            const response = await fetch(`${apiBaseUrl}/translate`, {
                method: "POST",
                body: formData,
            });

            if (response.ok) {
                setError("");
                setIsTranslate(true);
            } else {
                const errorData = await response.json();
                setError(errorData.message || "Error translating file");
            }
        } catch (err) {
            setError("Error translating file");
        } finally {
            setIsLoading(false);
        }
    };

    const download = async () => {
        if (!file) return;
        setIsLoading(true);
        try {
            const response = await fetch(
                `${apiBaseUrl}/download/${file.name}`,
                {
                    method: "GET",
                },
            );

            if (!response.ok) {
                throw new Error("Failed to download the file");
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.setAttribute("download", file.name);
            document.body.appendChild(link);
            link.click();
            link.remove();
        } catch (err) {
            setError("Error downloading file");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div id="app">
            <nav className="flex items-center p-4 bg-gray-800 text-white">
                <img src="/icon.png" alt="Leadable" className="w-7 h-7 mr-2" />
                <h1 className="text-2xl">Leadable</h1>
            </nav>
            <div className="container mx-auto p-4">
                <div
                    onDragEnter={dragEnter}
                    onDragLeave={dragLeave}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={dropFile}
                    className={`flex justify-center items-center bg-gray-200 rounded-lg p-2 border-dotted border-2 border-black mb-4 h-40 hover:bg-gray-300 ${isEnter ? "enter" : ""}`}
                >
                    <p className="text-lg">Drop pdf files here</p>
                </div>
                {error && (
                    <p className="w-full rounded-lg p-2 mb-4 bg-red-100 text-black">
                        {error}
                    </p>
                )}
                <div className="mb-4">
                    <p>{file ? file.name : ""}</p>
                </div>
                <button
                    id="translate"
                    onClick={translate}
                    type="button"
                    disabled={isLoading}
                    className="bg-indigo-600 rounded-lg p-2 mb-4 w-full text-white hover:bg-indigo-500 disabled:bg-indigo-300"
                >
                    Translate
                </button>
                {isTranslate && (
                    <button
                        id="download"
                        onClick={download}
                        type="button"
                        disabled={isLoading}
                        className="bg-sky-600 rounded-lg p-2 mb-4 w-full text-white hover:bg-indigo-500 disabled:bg-sky-300"
                    >
                        Download translated file
                    </button>
                )}
                {isLoading && (
                    <div className="flex justify-center" aria-label="読み込み中">
                        <div className="animate-spin h-10 w-10 border-4 border-blue-500 rounded-full border-t-transparent"></div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default App;
