import { Navigate, Route, Routes } from "react-router-dom";
import { Shell } from "./components/Shell";
import { StudioProvider } from "./state";
import { OverviewPage } from "./pages/OverviewPage";
import { ResearchPage } from "./pages/ResearchPage";
import { NewResearchPage } from "./pages/NewResearchPage";
import { WizardPage } from "./pages/WizardPage";
import { CampaignPage } from "./pages/CampaignPage";
import { ReviewsPage } from "./pages/ReviewsPage";
import { LibraryPage } from "./pages/LibraryPage";
import { TutorialPage } from "./pages/TutorialPage";
import { SettingsPage } from "./pages/SettingsPage";
import { AnalysisPage } from "./pages/AnalysisPage";
import { WorkflowPage } from "./pages/WorkflowPage";

export function App() {
  return (
    <StudioProvider>
      <Routes>
        <Route element={<Shell />}>
          <Route index element={<OverviewPage />} />
          <Route path="research" element={<ResearchPage />} />
          <Route path="research/new" element={<NewResearchPage />} />
          <Route
            path="research/:campaignId/design/:step"
            element={<WizardPage />}
          />
          <Route
            path="research/:campaignId/:section?"
            element={<CampaignPage />}
          />
          <Route path="reviews" element={<ReviewsPage />} />
          <Route path="analysis" element={<AnalysisPage />} />
          <Route path="workflow" element={<WorkflowPage />} />
          <Route path="library/:section" element={<LibraryPage />} />
          <Route path="tutorial" element={<TutorialPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </StudioProvider>
  );
}
