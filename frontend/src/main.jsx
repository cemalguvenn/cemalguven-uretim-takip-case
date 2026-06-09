import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App as AntApp, ConfigProvider, theme } from "antd";
import trTR from "antd/locale/tr_TR";
import dayjs from "dayjs";
import "dayjs/locale/tr";

import App from "./App.jsx";
import { brandTheme } from "./theme.js";
import "./index.css";

dayjs.locale("tr");

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ConfigProvider
      locale={trTR}
      theme={{ algorithm: theme.darkAlgorithm, token: brandTheme }}
    >
      <AntApp>
        <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <App />
        </BrowserRouter>
      </AntApp>
    </ConfigProvider>
  </React.StrictMode>
);
