import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { Layout } from "./components/Layout";
import { TraceList } from "./components/TraceList";
import { TraceDetail } from "./components/TraceDetail";
import { ReplayView } from "./components/ReplayView";

const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <TraceList /> },
      { path: "traces/:traceId", element: <TraceDetail /> },
      { path: "traces/:traceId/replay/:replayId", element: <ReplayView /> },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
