import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class MessageFormatter:
    """Service for formatting messages for Slack"""
    
    @staticmethod
    async def format_for_slack(response: str) -> str:
        """Format LLM response for better rendering in Slack"""
        if not response:
            return response
            
        # Process source citations section
        if "Sources used:" in response:
            # Split the response into main content and sources section
            main_content, sources_section = response.split("Sources used:", 1)
            
            # Format the sources section for better Slack rendering
            formatted_sources = []
            
            # Find all source citations with markdown links [text](url)
            link_pattern = r'\[(.*?)\]\((.*?)\)'
            
            # Preserve plain text sources and format URLs
            lines = sources_section.strip().split('\n')
            for line in lines:
                # Skip empty lines
                if not line.strip():
                    continue
                    
                # Format line with links
                if re.search(link_pattern, line):
                    # Slack format: <URL|text> 
                    formatted_line = re.sub(link_pattern, r'<\2|\1>', line)
                    formatted_sources.append(formatted_line)
                else:
                    # No links, keep as is
                    formatted_sources.append(line)
            
            # Combine formatted parts
            formatted_response = main_content + "Sources used:\n" + "\n".join(formatted_sources)
            return formatted_response
        
        return response
    
    @staticmethod
    def format_code_blocks(text: str) -> str:
        """Ensure code blocks are properly formatted for Slack"""
        # Slack requires ```language instead of ```python etc.
        pattern = r'```(\w+)'
        return re.sub(pattern, '```', text)
    
    @staticmethod
    def format_bullet_points(text: str) -> str:
        """Format bullet points for better Slack rendering"""
        # Replace GitHub-style bullets with Slack-compatible ones
        return text.replace('* ', '• ')
    
    @staticmethod
    async def format_message(text: Optional[str]) -> str:
        """Apply all formatting rules to a message"""
        if not text:
            return ""
            
        # Apply all formatting rules
        text = MessageFormatter.format_code_blocks(text)
        text = MessageFormatter.format_bullet_points(text)
        text = await MessageFormatter.format_for_slack(text)
        
        return text 