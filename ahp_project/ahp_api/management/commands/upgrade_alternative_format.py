from django.core.management.base import BaseCommand
from ahp_api.models import AHPProject
import datetime
import logging

class Command(BaseCommand):
    help = 'Upgrade alternative_matrices format for all projects'

    def handle(self, *args, **options):
        projects = AHPProject.objects.all()
        updated = 0
        skipped = 0
        errors = 0
        
        for project in projects:
            try:
                matrices = project.alternative_matrices
                alternatives = project.alternatives
                
                # Skip projects with no alternatives or matrices
                if not matrices or not alternatives:
                    skipped += 1
                    continue
                    
                # Skip projects already in new format
                if isinstance(matrices, dict) and isinstance(next(iter(matrices.values()), {}), dict):
                    skipped += 1
                    self.stdout.write(f"Project {project.id} already in new format, skipping")
                    continue
                
                # Convert to new format
                timestamp = datetime.datetime.now().isoformat()
                new_matrices = {
                    timestamp: {
                        'alternatives': alternatives,
                        'scores': matrices,
                        'ranking': project.ranking_list,
                        'final_scores': dict(zip(
                            project.ranking_list or [], 
                            project.alternative_scores or []
                        ))
                    }
                }
                
                # Save the new format
                project.alternative_matrices = new_matrices
                project.save(update_fields=['alternative_matrices'])
                updated += 1
                self.stdout.write(
                    self.style.SUCCESS(f"Updated format for project {project.id}")
                )
                
            except Exception as e:
                errors += 1
                self.stdout.write(
                    self.style.ERROR(f"Error updating project {project.id}: {str(e)}")
                )
                
        self.stdout.write(
            self.style.SUCCESS(
                f"Completed: {updated} projects updated, {skipped} skipped, {errors} errors"
            )
        )