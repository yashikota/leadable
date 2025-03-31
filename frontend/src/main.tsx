import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import {
  Route,
  RouterProvider,
  createBrowserRouter,
  createRoutesFromElements,
} from "react-router";

import App from "./App.tsx";
import { ResourceMonitor } from "./components/ResourceMonitor.tsx";
import { TaskDetail } from "./components/TaskDetail.tsx";

const router = createBrowserRouter(
  createRoutesFromElements(
    <Route>
      <Route path="/" element={<App />} />
      <Route path="/task/:task_id" element={<TaskDetail />} />
      <Route path="/resource" element={<ResourceMonitor />} />
    </Route>,
  ),
);

const container = document.getElementById("root");
if (!container) {
  throw new Error('Failed to find the element with id "root"');
}

createRoot(container).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
