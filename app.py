from __future__ import annotations

import streamlit as st

from agents.hpdc_agent import render_hpdc_agent
from services.config import load_settings
from services.github_loader import GitHubExcelLoader
from services.masterdata_service import MasterDataService


@st.cache_resource
def build_services() -> tuple[dict, MasterDataService]:
    settings = load_settings()
    loader = GitHubExcelLoader.from_settings(settings)
    service = MasterDataService(loader=loader, paths=settings["masterdata"])
    return settings, service


def main() -> None:
    settings, masterdata = build_services()
    st.set_page_config(page_title=settings["application"]["short_name"], page_icon="⚙️", layout="wide")
    st.title(settings["application"]["name"])
    st.sidebar.header("VEMCI")
    page = st.sidebar.radio("Technology", ["HPDC"])
    with st.sidebar.expander("Masterdata administration"):
        st.write(f"Repository: {settings['github']['owner']}/{settings['github']['repository']}")
        st.write(f"Branch: {settings['github']['branch']}")
        if st.button("Refresh masterdata cache"):
            deleted = masterdata.loader.clear_cache()
            st.cache_resource.clear()
            st.success(f"Cache cleared: {deleted} file(s). Reload the page to fetch fresh data.")
    if page == "HPDC":
        render_hpdc_agent(masterdata, settings)


if __name__ == "__main__":
    main()
