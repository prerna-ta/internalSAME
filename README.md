# Student Performance Analysis Dashboard

A comprehensive Streamlit dashboard for analyzing student performance data with Google Drive integration for cloud deployment.

## Features

- **📊 Overall Analysis**: Interactive charts and metrics showing student performance across subjects and teams
- **👨‍🎓 Individual Student Analysis**: Detailed view of individual student performance and progress tracking
- **📋 Data Management**: Complete data view with filtering and export capabilities
- **🔍 Advanced Filtering**: Multi-level filtering by team, form, period, school, grade, donor, and county
- **📈 Progress Tracking**: Visualize student performance trends over time
- **☁️ Cloud Integration**: Secure Google Drive integration for file storage and management

## Quick Start

### Local Development
1. Clone this repository
2. Install dependencies: `pip install -r requirements.txt`
3. Follow the setup guide in `QUICK_SETUP.md`
4. Run locally: `streamlit run streamlit_app.py`

### Cloud Deployment
Follow the comprehensive guide in `DEPLOYMENT_GUIDE.md` for deploying to Streamlit Cloud.

## File Structure
```
├── streamlit_app.py          # Main application file
├── requirements.txt          # Python dependencies
├── DEPLOYMENT_GUIDE.md       # Detailed deployment instructions
├── QUICK_SETUP.md           # Quick setup guide
├── secrets.toml.example     # Example secrets configuration
├── .gitignore              # Git ignore file
└── README.md               # This file
```

## Data Requirements

The dashboard expects the following Excel files in Google Drive:
- `Team Kathy Results.xlsx` - Team Kathy student performance data
- `Team Kelly A. Results.xlsx` - Team Kelly student performance data  
- `Team Lissette A.Results.xlsx` - Team Lissette student performance data
- `High School Data Sheet.xlsx` - Additional student information
- `SAM Elimu Logo-white_edited.png` - Organization logo

## Subject Categories

The dashboard analyzes performance across these subject categories:
- **Sciences**: Mathematics, Biology, Chemistry, Physics
- **Languages**: English, Kiswahili, French
- **Humanities**: History, Geography, CRE
- **Technical**: Computer Studies, Business Studies, Woodwork, Home Science, Agriculture

## Security Features

- Google Service Account authentication
- Secure credential management through Streamlit secrets
- No sensitive data stored in repository
- Encrypted data transmission

## Performance Optimizations

- Data caching (1-hour TTL) for improved performance
- Efficient file loading from Google Drive
- Responsive design for mobile and desktop
- Error handling and graceful fallbacks

## Getting Help

1. Check `QUICK_SETUP.md` for initial setup
2. Refer to `DEPLOYMENT_GUIDE.md` for deployment issues
3. Review Streamlit Cloud logs for error details
4. Verify Google Drive permissions and file IDs

## License

This project is licensed under the MIT License.